from __future__ import annotations

import re

from ..context import NormalizationContext
from ..pipeline import NormalizationStage
from ..text_utils import cleanup_punctuation_and_spaces


class ReferenceLinksStage(NormalizationStage):
    """
    Converts malformed reference-style Markdown links to plain URLs.
    
    Reference-style links consist of:
    - Link text in square brackets: [text]
    - Reference label in square brackets: [number or label]
    
    This stage converts [text][label] when there's no corresponding [label]: url definition:
    - If text looks like URL/domain → adds https:// prefix if missing
    - Otherwise → keeps text as-is
    
    Common artifact from LLM outputs.
    """
    name = "reference_links"

    # Matches reference-style links: [text][ref] or [text] [ref]
    RE_REFERENCE_LINK = re.compile(
        r'\[([^\]]+)\]\s*\[([^\]]+)\]'
    )
    
    # Pattern to detect domains/URLs
    # Matches: example.com, sub.example.com, github.com/path, etc.
    RE_DOMAIN = re.compile(
        r'^(?:https?://)?'  # Optional protocol
        r'(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'  # Domain
        r'(?:[^\s]*)?$',  # Optional path
        re.IGNORECASE
    )
    
    def apply(self, context: NormalizationContext) -> None:
        text = context.text
        
        # Find all reference-style links
        matches = list(self.RE_REFERENCE_LINK.finditer(text))
        
        if not matches:
            return
        
        # Extract all reference labels (the second bracket part)
        reference_labels = {match.group(2) for match in matches}
        
        # Check which references have definitions in the text
        # Reference definitions look like: [1]: https://example.com
        defined_references = set()
        for label in reference_labels:
            # Look for reference definitions at the start of lines
            definition_pattern = rf'^\s*\[{re.escape(label)}\]\s*:\s*\S+'
            if re.search(definition_pattern, text, re.MULTILINE):
                defined_references.add(label)
        
        # Convert undefined reference-style links
        converted_count = 0
        for match in reversed(matches):
            ref_label = match.group(2)
            if ref_label not in defined_references:
                # Extract the content from first brackets
                content = match.group(1)
                
                # Strip surrounding punctuation and spaces
                stripped_content = content.strip(' \t\n\r\f\v(),.;:!?\'"')
                
                # If stripped content looks like a domain/URL, add https:// if needed
                if stripped_content and self.RE_DOMAIN.match(stripped_content):
                    if not stripped_content.startswith(('http://', 'https://')):
                        replacement = f'https://{stripped_content}'
                    else:
                        replacement = stripped_content
                else:
                    # Plain text, keep as-is
                    replacement = content
                
                text = text[:match.start()] + replacement + text[match.end():]
                converted_count += 1
        
        if converted_count > 0:
            # Also remove any orphaned reference definitions
            for label in reference_labels:
                if label not in defined_references:
                    definition_pattern = rf'^\s*\[{re.escape(label)}\]\s*:.*$'
                    text = re.sub(definition_pattern, '', text, flags=re.MULTILINE)
            
            text = cleanup_punctuation_and_spaces(text)
            context.set_text(text)
            context.add_stat("reference_links", converted_count)
