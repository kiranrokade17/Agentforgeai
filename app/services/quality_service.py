import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.quality import CodeReview, QualityFinding, TestRun
from app.schemas.quality import QualityFindingItem, ReviewCreate, ReviewResponse, TestRunCreate, TestRunResponse


class QualityService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_test_run(self, data: TestRunCreate) -> TestRunResponse:
        task_id = uuid.UUID(data.task_id) if data.task_id else None
        run = TestRun(
            task_id=task_id,
            command=data.command,
            status=data.status,
            exit_code=data.exit_code,
            summary=data.summary,
            duration_ms=data.duration_ms,
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return TestRunResponse(
            id=str(run.id),
            task_id=str(run.task_id) if run.task_id else None,
            command=run.command,
            status=run.status,
            exit_code=run.exit_code,
            summary=run.summary,
            duration_ms=run.duration_ms,
            created_at=run.created_at.isoformat() if run.created_at else None,
        )

    async def create_review(self, data: ReviewCreate) -> ReviewResponse:
        task_id = uuid.UUID(data.task_id) if data.task_id else None
        review = CodeReview(task_id=task_id, summary=data.summary, status=data.status)
        self.session.add(review)
        await self.session.flush()

        created_findings: list[QualityFindingItem] = []
        for finding in data.findings:
            quality_finding = QualityFinding(
                review_id=review.id,
                severity=finding.severity,
                title=finding.title,
                file=finding.file,
                line=finding.line,
                description=finding.description,
            )
            self.session.add(quality_finding)
            created_findings.append(
                QualityFindingItem(
                    severity=quality_finding.severity,
                    title=quality_finding.title,
                    file=quality_finding.file,
                    line=quality_finding.line,
                    description=quality_finding.description,
                )
            )

        await self.session.commit()
        await self.session.refresh(review)
        return ReviewResponse(
            id=str(review.id),
            task_id=str(review.task_id) if review.task_id else None,
            summary=review.summary,
            status=review.status,
            findings=created_findings,
            created_at=review.created_at.isoformat() if review.created_at else None,
        )
