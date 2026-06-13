from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated, Generic, TypeVar

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlmodel import Field, SQLModel, Session, create_engine, select


class Campaign(SQLModel, table=True):
    campaign_id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    due_date: datetime | None = Field(default=None, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )


class CampaignCreate(SQLModel):
    name: str
    due_date: datetime | None = None


class CampaignRead(SQLModel):
    campaign_id: int
    name: str
    due_date: datetime | None = None
    created_at: datetime


T = TypeVar("T")


class Response(BaseModel, Generic[T]):
    data: T


sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()

    with Session(engine) as session:
        if not session.exec(select(Campaign)).first():
            session.add_all(
                [
                    Campaign(name="Summer Launch", due_date=datetime.now(timezone.utc)),
                    Campaign(name="BLACK FRIDAY", due_date=datetime.now(timezone.utc)),
                ]
            )
            session.commit()

    yield


app = FastAPI(root_path="/api/v1", lifespan=lifespan)


@app.get("/")
async def root():
    return {"message": "Hello world!"}


@app.get("/campaigns", response_model=Response[list[CampaignRead]])
async def read_campaigns(session: SessionDep):
    data = session.exec(select(Campaign)).all()
    return {"data": data}


@app.get("/campaigns/search", response_model=Response[list[CampaignRead]])
async def search_campaigns(q: str, session: SessionDep):
    data = session.exec(
        select(Campaign).where(Campaign.name.contains(q))
    ).all()

    return {"data": data}


@app.get("/campaigns-paginated", response_model=Response[list[CampaignRead]])
async def read_campaigns_paginated(
    session: SessionDep,
    offset: int = 0,
    limit: int = 10
):
    data = session.exec(
        select(Campaign).offset(offset).limit(limit)
    ).all()

    return {"data": data}


@app.get("/campaigns/{id}", response_model=Response[CampaignRead])
async def read_campaign_by_id(id: int, session: SessionDep):
    data = session.get(Campaign, id)

    if not data:
        raise HTTPException(
            status_code=404,
            detail="Campaign not found"
        )

    return {"data": data}


@app.post("/campaigns", status_code=201, response_model=Response[CampaignRead])
async def create_campaign(campaign: CampaignCreate, session: SessionDep):
    db_campaign = Campaign.model_validate(campaign)

    session.add(db_campaign)
    session.commit()
    session.refresh(db_campaign)

    return {"data": db_campaign}


@app.put("/campaigns/{id}", response_model=Response[CampaignRead])
async def update_campaign(id: int, campaign: CampaignCreate, session: SessionDep):
    data = session.get(Campaign, id)

    if not data:
        raise HTTPException(
            status_code=404,
            detail="Campaign not found"
        )

    data.name = campaign.name
    data.due_date = campaign.due_date

    session.add(data)
    session.commit()
    session.refresh(data)

    return {"data": data}


@app.delete("/campaigns/{id}", status_code=204)
async def delete_campaign(id: int, session: SessionDep):
    data = session.get(Campaign, id)

    if not data:
        raise HTTPException(
            status_code=404,
            detail="Campaign not found"
        )

    session.delete(data)
    session.commit()
