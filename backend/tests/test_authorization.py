"""Contrôle d'accès : isolation entre utilisateurs, rôles, confidentialité des classes."""

from collections.abc import Callable
from typing import Any

import jwt
from conftest import set_flags
from httpx import AsyncClient

from app.core.config import settings


async def _new_session(client: AsyncClient, account: Any) -> str:
    r = await client.post(
        "/api/chat/session", headers=account.headers, json={"subject": "mathematiques", "level": "lycee"}
    )
    return str(r.json()["session_id"])


async def test_user_cannot_read_or_use_someone_elses_session(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any
) -> None:
    alice, bob = await signup("alice"), await signup("bob")
    session_id = await _new_session(client, alice)

    assert (await client.get(f"/api/chat/history/{session_id}", headers=bob.headers)).status_code == 404
    assert (await client.get(f"/api/chat/session/{session_id}/info", headers=bob.headers)).status_code == 404
    msg = await client.post(
        "/api/chat/message",
        headers=bob.headers,
        json={"session_id": session_id, "message": "Salut", "subject": "mathematiques", "level": "lycee"},
    )
    assert msg.status_code == 404
    assert fake_llm.json_calls == 0


async def test_admin_endpoint_requires_admin_role(client: AsyncClient, signup: Callable[..., Any]) -> None:
    user = await signup("alice")
    assert (await client.get("/api/admin/stats", headers=user.headers)).status_code == 403
    assert (await client.get("/api/admin/stats")).status_code == 401
    await set_flags(user.email, is_admin=True)
    ok = await client.get("/api/admin/stats", headers=user.headers)
    assert ok.status_code == 200
    assert ok.json()["total_users"] == 1


async def test_role_is_read_from_database_not_from_token(
    client: AsyncClient, signup: Callable[..., Any]
) -> None:
    user = await signup("alice")
    await set_flags(user.email, is_admin=True)
    assert (await client.get("/api/admin/stats", headers=user.headers)).status_code == 200
    await set_flags(user.email, is_admin=False)  # même jeton : le retrait est immédiat
    assert (await client.get("/api/admin/stats", headers=user.headers)).status_code == 403


async def test_forged_token_is_rejected(client: AsyncClient, signup: Callable[..., Any]) -> None:
    user = await signup("alice")
    forged = jwt.encode(
        {"sub": "x", "type": "access", "tv": 0, "exp": 9999999999}, "wrong-key-" * 5, algorithm="HS256"
    )
    assert (
        await client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})
    ).status_code == 401
    none_alg = jwt.encode({"sub": "x", "type": "access", "exp": 9999999999}, "", algorithm="none")
    assert (
        await client.get("/api/auth/me", headers={"Authorization": f"Bearer {none_alg}"})
    ).status_code == 401
    assert user.headers  # le vrai jeton reste valide
    assert (await client.get("/api/auth/me", headers=user.headers)).status_code == 200
    assert settings.SECRET_KEY not in forged


async def test_teacher_only_sees_own_classrooms(client: AsyncClient, signup: Callable[..., Any]) -> None:
    teacher1, teacher2, student = await signup("prof1"), await signup("prof2"), await signup("eleve")
    await set_flags(teacher1.email, is_teacher=True)
    await set_flags(teacher2.email, is_teacher=True)

    assert (
        await client.post(
            "/api/classrooms/", headers=student.headers, json={"name": "Nope", "level": "lycee"}
        )
    ).status_code == 403

    created = await client.post(
        "/api/classrooms/", headers=teacher1.headers, json={"name": "Terminale C", "level": "lycee"}
    )
    assert created.status_code == 200
    classroom = created.json()

    joined = await client.post(
        "/api/classrooms/join",
        headers=student.headers,
        json={"invite_code": classroom["invite_code"].lower()},
    )
    assert joined.status_code == 200 and joined.json()["already_member"] is False

    report = await client.get(f"/api/classrooms/{classroom['id']}/report", headers=teacher1.headers)
    assert report.status_code == 200
    assert [s["username"] for s in report.json()["students"]] == ["eleve"]

    # Un autre enseignant ne peut pas deviner l'identifiant de la classe.
    assert (
        await client.get(f"/api/classrooms/{classroom['id']}/report", headers=teacher2.headers)
    ).status_code == 404
    # Un élève non plus.
    assert (
        await client.get(f"/api/classrooms/{classroom['id']}/report", headers=student.headers)
    ).status_code == 403


async def test_student_can_leave_classroom(client: AsyncClient, signup: Callable[..., Any]) -> None:
    teacher, student = await signup("prof"), await signup("eleve")
    await set_flags(teacher.email, is_teacher=True)
    classroom = (
        await client.post(
            "/api/classrooms/", headers=teacher.headers, json={"name": "6e A", "level": "college"}
        )
    ).json()
    await client.post(
        "/api/classrooms/join", headers=student.headers, json={"invite_code": classroom["invite_code"]}
    )

    joined = await client.get("/api/classrooms/joined", headers=student.headers)
    assert [c["id"] for c in joined.json()] == [classroom["id"]]

    left = await client.delete(f"/api/classrooms/membership/{classroom['id']}", headers=student.headers)
    assert left.status_code == 200
    report = await client.get(f"/api/classrooms/{classroom['id']}/report", headers=teacher.headers)
    assert report.json()["students"] == []
    assert (
        await client.delete(f"/api/classrooms/membership/{classroom['id']}", headers=student.headers)
    ).status_code == 404


async def test_invalid_enum_values_are_rejected(client: AsyncClient, signup: Callable[..., Any]) -> None:
    user = await signup("alice")
    r = await client.post(
        "/api/chat/session", headers=user.headers, json={"subject": "astrologie", "level": "lycee"}
    )
    assert r.status_code == 422
