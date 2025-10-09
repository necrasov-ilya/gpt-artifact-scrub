from __future__ import annotations

import re

from ..context import NormalizationContext
from ..pipeline import NormalizationStage
from ..text_utils import cleanup_punctuation_and_spaces


class ReferenceLinksStage(NormalizationStage):
    """
    Converts malformed reference-style Markdown links [text][label] to plain URLs.
    
    When [label]: url definition is missing:
    - Domain-like text → adds https:// prefix (e.g., ssi.inc → https://ssi.inc)
    - Plain text → extracts as-is
    
    Common artifact from LLM outputs.
    """
    name = "reference_links"

    RE_REFERENCE_LINK = re.compile(r'\[([^\]]+)\]\s*\[([^\]]+)\]')
    RE_DOMAIN = re.compile(
        r'^(?:https?://)?(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:[^\s]*)?$',
        re.IGNORECASE
    )
    
    def apply(self, context: NormalizationContext) -> None:
        text = context.text
        matches = list(self.RE_REFERENCE_LINK.finditer(text))
        if not matches:
            return
        
        # Find which reference labels have definitions ([label]: url)
        reference_labels = {match.group(2) for match in matches}
        defined_references = set()
        for label in reference_labels:
            pattern = rf'^\s*\[{re.escape(label)}\]\s*:\s*\S+'
            if re.search(pattern, text, re.MULTILINE):
                defined_references.add(label)
        
        # Convert undefined reference links
        converted_count = 0
        for match in reversed(matches):
            if match.group(2) not in defined_references:
                content = match.group(1).strip(' \t\n\r\f\v(),.;:!?\'"')
                
                # Check if looks like domain/URL
                if content and self.RE_DOMAIN.match(content):
                    replacement = content if content.startswith(('http://', 'https://')) else f'https://{content}'
                else:
                    replacement = match.group(1)  # Keep original content for plain text
                
                text = text[:match.start()] + replacement + text[match.end():]
                converted_count += 1
        
        if converted_count > 0:
            context.set_text(cleanup_punctuation_and_spaces(text))
            context.add_stat("reference_links", converted_count)
