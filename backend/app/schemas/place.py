from pydantic import BaseModel, ConfigDict

from app.models import PlaceKind


class PlaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    kind: PlaceKind
