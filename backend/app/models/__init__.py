from app.models.association import PaperAuthor, PaperTopic
from app.models.author import Author
from app.models.paper import Paper
from app.models.similarity import PaperSimilarity
from app.models.topic import Topic

__all__ = [
    "Paper",
    "Author",
    "Topic",
    "PaperAuthor",
    "PaperTopic",
    "PaperSimilarity",
]
