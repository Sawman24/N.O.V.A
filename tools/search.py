from duckduckgo_search import DDGS
import json

def search_web(query: str, max_results: int = 5) -> str:
    """Searches the web for a given query and returns snippets of the top results. 
    Use this tool to find up-to-date information, facts, or context on the web."""
    try:
        results = []
        with DDGS() as ddgs:
            # text() returns a generator of dictionaries with 'title', 'href', 'body'
            for r in ddgs.text(query, max_results=max_results):
                results.append(r)
                
        if not results:
            return f"No results found for '{query}'."
            
        formatted_results = []
        for i, res in enumerate(results, 1):
            title = res.get('title', 'No title')
            link = res.get('href', 'No link')
            snippet = res.get('body', 'No snippet available')
            
            formatted_results.append(
                f"Result {i}:\n"
                f"Title: {title}\n"
                f"URL: {link}\n"
                f"Snippet: {snippet}\n"
            )
            
        return "\n".join(formatted_results)
    except Exception as e:
        return f"Error performing web search: {e}"
