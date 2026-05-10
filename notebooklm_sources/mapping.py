from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl


NOTEBOOK_ID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "courses.yaml"


class SourcesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: HttpUrl | None = None
    traverse: list[str] = Field(default_factory=list)
    collect: list[str] = Field(default_factory=list)
    include_text: list[str] = Field(default_factory=list)
    exclude_text: list[str] = Field(default_factory=list)
    pages: list[HttpUrl] = Field(default_factory=list)


class Echo360Config(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str


class CourseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: SourcesConfig
    notebook_id: str | None = Field(default=None, pattern=NOTEBOOK_ID_PATTERN)
    echo360: Echo360Config | None = None
    upload_original: bool = False


class CoursesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    courses: dict[str, CourseConfig]


def load_mapping(path: Path | str = DEFAULT_CONFIG_PATH) -> dict[str, CourseConfig]:
    config_path = Path(path)
    data = yaml.safe_load(config_path.read_text())
    return CoursesConfig.model_validate(data).courses
