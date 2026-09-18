import uuid

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from flowraga.auth.dependencies import CurrentUser
from flowraga.db.dependencies import DbSession
from flowraga.db.models import AnswerFeedback, ChatConversation, ChatMessage, Project
from flowraga.schemas.conversations import (
    ConversationDetail,
    ConversationResponse,
    FeedbackRequest,
    FeedbackResponse,
)

router = APIRouter(prefix="/projects/{project_id}/conversations", tags=["conversations"])


async def require_project(project_id: uuid.UUID, owner_id: uuid.UUID, db: DbSession) -> None:
    project = await db.scalar(
        select(Project).where(Project.id == project_id, Project.owner_id == owner_id)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")


async def owned_conversation(
    project_id: uuid.UUID, conversation_id: uuid.UUID, owner_id: uuid.UUID, db: DbSession
) -> ChatConversation:
    conversation = await db.scalar(
        select(ChatConversation)
        .options(selectinload(ChatConversation.messages))
        .where(
            ChatConversation.id == conversation_id,
            ChatConversation.project_id == project_id,
            ChatConversation.owner_id == owner_id,
        )
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    project_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> list[ChatConversation]:
    await require_project(project_id, user.id, db)
    items = await db.scalars(
        select(ChatConversation)
        .where(
            ChatConversation.project_id == project_id,
            ChatConversation.owner_id == user.id,
        )
        .order_by(ChatConversation.updated_at.desc())
    )
    return list(items)


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    project_id: uuid.UUID, conversation_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> ChatConversation:
    conversation = await owned_conversation(project_id, conversation_id, user.id, db)
    conversation.messages.sort(key=lambda message: message.created_at)
    return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    project_id: uuid.UUID, conversation_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> None:
    conversation = await owned_conversation(project_id, conversation_id, user.id, db)
    await db.delete(conversation)


@router.get("/{conversation_id}/export")
async def export_conversation(
    project_id: uuid.UUID, conversation_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> Response:
    conversation = await owned_conversation(project_id, conversation_id, user.id, db)
    messages = sorted(conversation.messages, key=lambda message: message.created_at)
    lines = [f"# {conversation.title}", ""]
    for message in messages:
        lines.extend([f"## {message.role.title()}", "", message.content, ""])
        if message.sources:
            lines.extend(
                f"- [{source['label']}] {source['filename']} (score {source['score']})"
                for source in message.sources
            )
            lines.append("")
    return Response(
        "\n".join(lines),
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="conversation-{conversation.id}.md"'
        },
    )


@router.put("/{conversation_id}/messages/{message_id}/feedback", response_model=FeedbackResponse)
async def save_feedback(
    project_id: uuid.UUID,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    payload: FeedbackRequest,
    db: DbSession,
    user: CurrentUser,
) -> AnswerFeedback:
    await owned_conversation(project_id, conversation_id, user.id, db)
    message = await db.scalar(
        select(ChatMessage).where(
            ChatMessage.id == message_id,
            ChatMessage.conversation_id == conversation_id,
            ChatMessage.owner_id == user.id,
            ChatMessage.role == "assistant",
        )
    )
    if message is None:
        raise HTTPException(status_code=404, detail="Answer not found")
    feedback = await db.scalar(
        select(AnswerFeedback).where(AnswerFeedback.message_id == message.id)
    )
    if feedback is None:
        feedback = AnswerFeedback(message_id=message.id, owner_id=user.id, rating=payload.rating)
        db.add(feedback)
    feedback.rating = payload.rating
    feedback.comment = payload.comment
    await db.flush()
    await db.refresh(feedback)
    return feedback
