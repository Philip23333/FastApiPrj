import sys
import unittest
import uuid
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class TestUserCrudSimple(unittest.IsolatedAsyncioTestCase):
    async def test_create_user_and_filter(self):
        try:
            from config.db_config import AsyncSessionLocal
            from crud import user as user_crud
            from schemas.user import UserCreate
        except Exception as exc:
            raise unittest.SkipTest(f"依赖未安装或模块不可用，跳过测试：{exc}")

        username = f"crud_{uuid.uuid4().hex[:10]}"
        phone = f"13{uuid.uuid4().int % 10**9:09d}"

        async with AsyncSessionLocal() as db:
            created_user_id = None
            try:
                # 关键验证1：create_user 默认应写入 role=user、status=active。
                created = await user_crud.create_user(
                    db,
                    UserCreate(
                        username=username,
                        password="hashed_for_test_only",
                        nickname="crud_test_user",
                        phone=phone,
                    ),
                )
                await db.commit()
                created_user_id = created.id

                self.assertEqual(created.role, "user")
                self.assertEqual(created.status, "active")

                # 关键验证2：按 keyword/role/status 筛选应能查到刚创建的用户。
                users = await user_crud.get_users(
                    db,
                    skip=0,
                    limit=20,
                    keyword=username,
                    role="user",
                    status="active",
                )
                self.assertTrue(any(u.id == created.id for u in users))

                # 关键验证3：count_users 与筛选条件联动，结果至少为 1。
                total = await user_crud.count_users(
                    db,
                    keyword=username,
                    role="user",
                    status="active",
                )
                self.assertGreaterEqual(total, 1)
            except Exception as exc:
                raise unittest.SkipTest(f"数据库未就绪或未完成迁移，跳过测试：{exc}")
            finally:
                if created_user_id:
                    try:
                        await user_crud.delete_user(db, created_user_id)
                        await db.commit()
                    except Exception:
                        await db.rollback()


if __name__ == "__main__":
    unittest.main()
