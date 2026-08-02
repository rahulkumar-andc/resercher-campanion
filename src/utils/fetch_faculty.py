import os
import sys
import json
import requests
import argparse

# Add root to python path so we can import our agents
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.core.models import PipelineContext
from src.core.event_bus import SupervisorBus
from process_faculty import FacultyProfileAgent

def search_author_openalex(author_name: str) -> dict:
    """Search for an author on OpenAlex and return their ID and display name."""
    print(f"[*] Searching OpenAlex for author: {author_name}")
    url = f"https://api.openalex.org/authors?search={requests.utils.quote(author_name)}"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    
    if not data.get("results"):
        print(f"[-] No author found for '{author_name}'")
        return None
        
    # Assume the first result is the best match
    best_match = data["results"][0]
    author_id = best_match["id"].split("/")[-1]
    display_name = best_match["display_name"]
    institution = best_match.get("last_known_institution", {}).get("display_name", "Unknown Institution")
    
    print(f"[+] Found author: {display_name} ({author_id}) at {institution}")
    return {
        "id": author_id,
        "name": display_name,
        "institution": institution
    }

def fetch_author_works(author_id: str, max_works: int = 15) -> list:
    """Fetch recent/top works for an author from OpenAlex."""
    print(f"[*] Fetching up to {max_works} works for author ID {author_id}...")
    url = f"https://api.openalex.org/works?filter=author.id:{author_id}&sort=publication_year:desc&per-page={max_works}"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    
    works = []
    for work in data.get("results", []):
        title = work.get("title", "Untitled")
        year = work.get("publication_year", "Unknown")
        loc = work.get("primary_location") or {}
        source = loc.get("source") or {}
        journal = source.get("display_name", "Unknown Journal")
        
        # Extract co-authors
        authors = []
        for authorship in work.get("authorships", []):
            authors.append(authorship.get("author", {}).get("display_name", ""))
            
        # Extract concepts (tags)
        concepts = [c["display_name"] for c in work.get("concepts", [])[:5]]
        
        works.append({
            "title": title,
            "year": year,
            "journal": journal,
            "authors": [a for a in authors if a],
            "tags": concepts
        })
        
    print(f"[+] Fetched {len(works)} works.")
    return works

def generate_synthetic_cv(author_data: dict, works: list) -> str:
    """Generate a markdown CV string from the OpenAlex data."""
    cv = f"Title\nProfessor\n"
    cv += f"Name\n{author_data['name']}\n"
    cv += f"Institution\n{author_data['institution']}\n\n"
    
    cv += "Career Profile\n"
    cv += f"{author_data['name']} is a researcher at {author_data['institution']}. Their work primarily spans the concepts found in their publications below.\n\n"
    
    cv += "Publications\n"
    for w in works:
        authors_str = ", ".join(w["authors"])
        tags_str = ", ".join(w["tags"])
        cv += f"- {w['title']}\n"
        cv += f"  Authors: {authors_str}\n"
        cv += f"  Journal: {w['journal']}\n"
        cv += f"  Year: {w['year']}\n"
        cv += f"  Keywords: {tags_str}\n\n"
        
    return cv

def main():
    parser = argparse.ArgumentParser(description="Automate Faculty Profile extraction using OpenAlex.")
    parser.add_argument("name", type=str, help="Name of the faculty member to search for")
    args = parser.parse_args()

    # 1. Fetch data from OpenAlex
    author_data = search_author_openalex(args.name)
    if not author_data:
        sys.exit(1)
        
    works = fetch_author_works(author_data["id"])
    
    # 2. Generate unstructured text (synthetic CV)
    synthetic_cv = generate_synthetic_cv(author_data, works)
    
    # 3. Process through LLM Agent
    print(f"[*] Running FacultyProfileAgent on the synthesized data...")
    bus = SupervisorBus()
    ctx = PipelineContext(
        job_id="openalex-fetch",
        raw_topic=synthetic_cv  # We hijack raw_topic to pass the CV text
    )
    
    agent = FacultyProfileAgent(bus)
    agent.run(ctx)
    print(f"[+] Automation complete. Profile should be saved in output/faculty_profiles/")

if __name__ == "__main__":
    main()
