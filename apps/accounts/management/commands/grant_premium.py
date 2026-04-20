"""
管理コマンド: 指定ユーザーにプレミアムを付与する（TestFlight・開発用）

使い方:
  python manage.py grant_premium <email> [--days 30]

例:
  python manage.py grant_premium tester@example.com
  python manage.py grant_premium tester@example.com --days 90
  python manage.py grant_premium tester@example.com --revoke   # 解除
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class Command(BaseCommand):
    help = 'TestFlight / 開発用: 指定ユーザーにプレミアムを付与・解除する'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='対象ユーザーのメールアドレス')
        parser.add_argument(
            '--days', type=int, default=30,
            help='有効日数（デフォルト: 30日）'
        )
        parser.add_argument(
            '--revoke', action='store_true',
            help='プレミアムを解除してフリープランに戻す'
        )

    def handle(self, *args, **options):
        email = options['email']
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise CommandError(f'ユーザーが見つかりません: {email}')

        if options['revoke']:
            user.subscription_tier = 'free'
            user.subscription_expires_at = None
            user.save(update_fields=['subscription_tier', 'subscription_expires_at'])
            self.stdout.write(self.style.WARNING(
                f'✗ {email} のプレミアムを解除しました（フリープランに戻しました）'
            ))
        else:
            days = options['days']
            user.subscription_tier = 'premium'
            user.subscription_expires_at = timezone.now() + timedelta(days=days)
            user.save(update_fields=['subscription_tier', 'subscription_expires_at'])
            self.stdout.write(self.style.SUCCESS(
                f'✓ {email} にプレミアムを付与しました（{days}日間 / '
                f'期限: {user.subscription_expires_at.strftime("%Y-%m-%d")}）'
            ))
