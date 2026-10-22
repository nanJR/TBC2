"""/actions: next steps drafted by the AI agent, waiting for a person to decide.

Human-in-the-loop rule: nothing is ever sent unless a person approves it here.
(For now, approving only changes the status. Nothing is actually sent.)
"""

from fastapi import APIRouter, HTTPException

from app.mock_data import ACTIONS
from app.schemas import Action, ActionStatus

router = APIRouter(prefix="/actions", tags=["actions"])


@router.get("", response_model=list[Action])
def list_actions(status: ActionStatus | None = None) -> list[Action]:
    """All actions, or only those with the given status (e.g. ?status=pending)."""
    return [a for a in ACTIONS.values() if status is None or a.status == status]


def _decide(action_id: int, new_status: ActionStatus) -> Action:
    action = ACTIONS.get(action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")
    if action.status != "pending":
        raise HTTPException(status_code=409, detail=f"Action already {action.status}")
    action.status = new_status
    return action


@router.post("/{action_id}/approve", response_model=Action)
def approve(action_id: int) -> Action:
    return _decide(action_id, "approved")


@router.post("/{action_id}/reject", response_model=Action)
def reject(action_id: int) -> Action:
    return _decide(action_id, "rejected")
