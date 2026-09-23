from celery import Celery
from config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

celery_app = Celery(
    'ai_photo',
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='Asia/Shanghai',
    enable_utc=True,
    task_track_started=True,
    result_expires=3600,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)


@celery_app.task(bind=True, name='auto_edit')
def auto_edit_task(self, raw_path: str, feedback: str = None):
    from ai_agent import PhotoEditOrchestrator

    try:
        self.update_state(
            state='PROGRESS',
            meta={'step': 'analyzing', 'message': 'AI 分析中...'}
        )

        orchestrator = PhotoEditOrchestrator()

        self.update_state(
            state='PROGRESS',
            meta={'step': 'editing', 'message': '执行修图...'}
        )

        if feedback:
            result = orchestrator.edit_with_feedback(raw_path, feedback)
        else:
            result = orchestrator.auto_edit(raw_path)

        self.update_state(
            state='PROGRESS',
            meta={'step': 'done', 'message': '完成'}
        )

        return {
            'output_path': result['output_path'],
            'tools_executed': result['tools_executed'],
            'analysis': result.get('analysis', {}),
        }

    except Exception as e:
        logger.exception(f"任务失败: {e}")
        raise