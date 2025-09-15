from pydantic import BaseModel
from uuid import UUID, uuid5

NAMESPACE_UUID = "99b800cb-edff-4c1a-9917-4910ea917a47"

class MarkdownPage(BaseModel):
    id: str = None
    url: str
    title: str
    content: str

    def generate_doc_id(self) -> None:
        """Generates a stable ID for a document."""
        namespace = UUID(NAMESPACE_UUID)
        self.id = str(uuid5(namespace, f"{self.title}:{self.content}"))
    


class ExtractedDocument(BaseModel):
    doc_id: str
    url: str
    title: str
    content: str