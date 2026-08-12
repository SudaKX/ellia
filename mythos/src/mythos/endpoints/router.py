from fastapi import APIRouter

from mythos.endpoints.accounts import router as accounts_router
from mythos.endpoints.achievements import router as achievements_router
from mythos.endpoints.auth import router as auth_router
from mythos.endpoints.credits import router as credits_router
from mythos.endpoints.files import router as files_router
from mythos.endpoints.hints import router as hints_router
from mythos.endpoints.progress import router as progress_router
from mythos.endpoints.scripts import router as scripts_router
from mythos.endpoints.tasks import router as tasks_router
from mythos.endpoints.validations import router as validations_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(achievements_router)
router.include_router(accounts_router)
router.include_router(files_router)
router.include_router(hints_router)
router.include_router(credits_router)
router.include_router(progress_router)
router.include_router(scripts_router)
router.include_router(validations_router)
router.include_router(tasks_router)

__all__ = ["router"]
