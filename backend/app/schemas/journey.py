from pydantic import ConfigDict

from app.domain.journey import ProjectJourneyRecord


class ProjectJourneyRead(ProjectJourneyRecord):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


__all__ = ["ProjectJourneyRead"]
