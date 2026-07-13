from app.db.database import Base, engine
from app.models import AssistantResponse, MeetingSession, TranscriptSegment


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    initialize_database()

    print("Database tables created successfully.")
