import os
import sys
import json
import pymysql
import bcrypt

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import settings


def hash_password(password: str) -> str:
    pwd_bytes = str(password).encode("utf-8")[:72]
    hashed = bcrypt.hashpw(pwd_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def ensure_index(cursor, table: str, index_name: str, columns: str):
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND INDEX_NAME = %s;
        """,
        (table, index_name),
    )
    if cursor.fetchone()[0] == 0:
        cursor.execute(f"ALTER TABLE {table} ADD INDEX {index_name} ({columns});")
        print(f"Added index '{index_name}' to '{table}'.")


def init_database():
    print(f"Connecting to MySQL database: {settings.DB_NAME}...")
    connection = pymysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            # 1. Tạo Database
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS {settings.DB_NAME} "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
            cursor.execute(f"USE {settings.DB_NAME};")

            # 2. Tạo bảng users
            create_users_table_query = """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                full_name VARCHAR(100) NOT NULL,
                email VARCHAR(255) NOT NULL UNIQUE,
                hashed_password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
            cursor.execute(create_users_table_query)
            print("Table 'users' created or already exists.")

            # 3. Seed tài khoản mẫu vào users
            sample_users = [
                ("Tiến Đạt (Admin)", "tiendat.admin@example.com", hash_password("Admin123@")),
                ("Member One", "member1@example.com", hash_password("Password123!")),
                ("Member Two", "member2@example.com", hash_password("Password123!")),
            ]
            seed_users_query = """
            INSERT IGNORE INTO users (full_name, email, hashed_password)
            VALUES (%s, %s, %s);
            """
            cursor.executemany(seed_users_query, sample_users)
            print("Seeded sample users into 'users' table.")

            # 4. Tạo bảng templates khớp 100% với model Template
            create_templates_table_query = """
            CREATE TABLE IF NOT EXISTS templates (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                description TEXT NULL,
                thumbnail_url VARCHAR(255) NULL,
                file_path VARCHAR(255) NOT NULL,
                placeholders JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
            cursor.execute(create_templates_table_query)
            print("Table 'templates' created or already exists.")

            # 5. Seed 3 mẫu template chuẩn (id=1: sales.html, id=2: marketing.html, id=3: event.html)
            standard_placeholders = json.dumps([
                "headline",
                "subheadline",
                "features",
                "cta_text",
                "primary_color",
                "image_url",
            ])

            sample_templates = [
                (
                    1,
                    "Sales Landing Page",
                    "Mẫu landing page tối ưu chuyển đổi bán hàng và chốt đơn trực tiếp.",
                    "/static/thumbnails/modern_tech.jpg",
                    "sales.html",
                    standard_placeholders,
                ),
                (
                    2,
                    "Marketing Landing Page",
                    "Mẫu landing page quảng bá sản phẩm, thương hiệu và thu hút khách hàng tiềm năng.",
                    "/static/thumbnails/elegant_beauty.jpg",
                    "marketing.html",
                    standard_placeholders,
                ),
                (
                    3,
                    "Event Landing Page",
                    "Mẫu landing page giới thiệu sự kiện, hội thảo và đăng ký tham gia.",
                    "/static/thumbnails/trust_consulting.jpg",
                    "event.html",
                    standard_placeholders,
                ),
            ]
            seed_templates_query = """
            INSERT IGNORE INTO templates (id, name, description, thumbnail_url, file_path, placeholders)
            VALUES (%s, %s, %s, %s, %s, %s);
            """
            cursor.executemany(seed_templates_query, sample_templates)
            print("Seeded 3 sample templates into 'templates' table.")

            # 6. Tạo bảng projects
            create_projects_table_query = """
            CREATE TABLE IF NOT EXISTS projects (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                template_id INT NOT NULL,
                campaign_name VARCHAR(255) NOT NULL,
                product_name VARCHAR(255) NOT NULL,
                product_description TEXT NULL,
                price DECIMAL(12,2) NULL,
                image_url VARCHAR(500) NULL,
                color_theme VARCHAR(50) NULL,
                messenger_link VARCHAR(500) NULL,
                tiktok_shop_link VARCHAR(500) NULL,
                zalo_link VARCHAR(500) NULL,
                instagram_link VARCHAR(500) NULL,
                hotline VARCHAR(50) NULL,
                facebook_url VARCHAR(500) NULL,
                tiktok_url VARCHAR(500) NULL,
                instagram_url VARCHAR(500) NULL,
                repo_url VARCHAR(500) NULL,
                github_pages_url VARCHAR(500) NULL,
                raw_json_data JSON NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'draft',
                deleted_at DATETIME NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                CONSTRAINT fk_projects_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT fk_projects_template FOREIGN KEY (template_id) REFERENCES templates(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
            cursor.execute(create_projects_table_query)
            print("Table 'projects' created or already exists.")

            # 6.1. Bổ sung cột deleted_at cho database cũ (soft delete landing page)
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s
                  AND TABLE_NAME = 'projects'
                  AND COLUMN_NAME = 'deleted_at'
                """,
                (settings.DB_NAME,),
            )
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    "ALTER TABLE projects ADD COLUMN deleted_at DATETIME NULL AFTER updated_at;"
                )
                print("Added missing column 'deleted_at' to 'projects' table.")
            else:
                print("Column 'deleted_at' already exists on 'projects' table.")

            # 6.2. Bổ sung các cột CTA động còn thiếu cho database cũ
            cta_columns = {
                "messenger_link": "VARCHAR(500) NULL",
                "tiktok_shop_link": "VARCHAR(500) NULL",
                "zalo_link": "VARCHAR(500) NULL",
                "instagram_link": "VARCHAR(500) NULL",
                "hotline": "VARCHAR(50) NULL",
            }
            for column_name, column_type in cta_columns.items():
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = %s
                      AND TABLE_NAME = 'projects'
                      AND COLUMN_NAME = %s
                    """,
                    (settings.DB_NAME, column_name),
                )
                if cursor.fetchone()[0] == 0:
                    cursor.execute(
                        f"ALTER TABLE projects ADD COLUMN {column_name} {column_type};"
                    )
                    print(f"Added missing column '{column_name}' to 'projects' table.")

            # 7. Tạo bảng project_versions
            create_project_versions_table_query = """
            CREATE TABLE IF NOT EXISTS project_versions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                project_id INT NOT NULL,
                version_number INT NOT NULL,
                json_content JSON NULL,
                html_snapshot LONGTEXT NOT NULL,
                commit_sha VARCHAR(40) NULL,
                change_summary VARCHAR(255) NULL,
                created_by INT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX ix_project_versions_project_id (project_id),
                CONSTRAINT uq_project_version UNIQUE (project_id, version_number),
                CONSTRAINT fk_versions_project FOREIGN KEY (project_id)
                    REFERENCES projects(id) ON DELETE CASCADE,
                CONSTRAINT fk_versions_user FOREIGN KEY (created_by)
                    REFERENCES users(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
            cursor.execute(create_project_versions_table_query)
            print("Table 'project_versions' created or already exists.")

            # 8. Tạo bảng deployments
            create_deployments_table_query = """
            CREATE TABLE IF NOT EXISTS deployments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                project_id INT NOT NULL,
                commit_sha VARCHAR(100) NOT NULL,
                status VARCHAR(50) DEFAULT 'Pending',
                github_pages_url VARCHAR(255) NULL,
                error_message TEXT NULL,
                start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                end_time DATETIME NULL,
                CONSTRAINT fk_deployments_project FOREIGN KEY (project_id)
                    REFERENCES projects(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
            cursor.execute(create_deployments_table_query)
            print("Table 'deployments' created or already exists.")
            # 9. Tạo bảng generations (lưu lịch sử sinh nội dung bằng Gemini)
            create_generations_table_query = """
            CREATE TABLE IF NOT EXISTS generations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                project_id INT NOT NULL,
                prompt TEXT NOT NULL,
                response_json JSON NULL,
                status VARCHAR(20) NOT NULL,
                error_message TEXT NULL,
                created_at DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
                INDEX ix_generations_project_id (project_id),
                CONSTRAINT fk_generations_project_id FOREIGN KEY (project_id)
                    REFERENCES projects(id) ON DELETE CASCADE,
                CONSTRAINT chk_generations_status CHECK (status IN ('pending', 'success', 'failed'))
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
            cursor.execute(create_generations_table_query)
            print("Table 'generations' created or already exists.")

            # 10. Siết NOT NULL cho deployments
            cursor.execute("UPDATE deployments SET status = 'Pending' WHERE status IS NULL;")
            cursor.execute("UPDATE deployments SET start_time = NOW() WHERE start_time IS NULL;")
            cursor.execute(
                "ALTER TABLE deployments MODIFY status VARCHAR(50) NOT NULL DEFAULT 'Pending';"
            )
            cursor.execute(
                "ALTER TABLE deployments MODIFY start_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP;"
            )

            # 11. Đảm bảo các index cần thiết
            ensure_index(cursor, "projects", "idx_projects_user_status_updated", "user_id, status, updated_at")
            ensure_index(cursor, "deployments", "idx_deployments_project_start", "project_id, start_time")
            print("Constraints and indexes reviewed.")

            # 12. Seed dữ liệu mẫu demo
            cursor.execute(
                "SELECT id, email FROM users WHERE email IN (%s, %s);",
                ("member1@example.com", "member2@example.com"),
            )
            user_map = {row[1]: row[0] for row in cursor.fetchall()}
            member1_id = user_map.get("member1@example.com")
            member2_id = user_map.get("member2@example.com")

            created = 0
            if member1_id and member2_id:
                demo_projects = [
                    {
                        "user_id": member1_id,
                        "template_id": 1,
                        "campaign_name": "Demo Khuyen mai thu dong",
                        "product_name": "Thoi trang Thu Dong",
                        "product_description": "Bo suu tap thoi trang thu dong phong cach tre trung va am ap.",
                        "price": 890000,
                        "color_theme": "#4F46E5",
                        "facebook_url": "https://facebook.com/demo.khuyenmai",
                        "tiktok_url": "https://tiktok.com/@demo.khuyenmai",
                        "instagram_url": "https://instagram.com/demo.khuyenmai",
                        "status": "published",
                    },
                    {
                        "user_id": member1_id,
                        "template_id": 2,
                        "campaign_name": "Demo Ra mat my pham",
                        "product_name": "My pham thien nhien",
                        "product_description": "Bo san pham cham soc da va my pham cao cap chiet xuat thien nhien.",
                        "price": 450000,
                        "color_theme": "#10B981",
                        "facebook_url": None,
                        "tiktok_url": None,
                        "instagram_url": None,
                        "status": "draft",
                    },
                    {
                        "user_id": member1_id,
                        "template_id": 3,
                        "campaign_name": "Demo Hoi thao marketing",
                        "product_name": "Ve tham du hoi thao Marketing",
                        "product_description": "Chuong trinh hoi thao chuyen sau ve chien luoc marketing va tang truong.",
                        "price": 0,
                        "color_theme": "#F59E0B",
                        "facebook_url": None,
                        "tiktok_url": None,
                        "instagram_url": None,
                        "status": "failed",
                    },
                    {
                        "user_id": member2_id,
                        "template_id": 1,
                        "campaign_name": "Demo cua Member Two A",
                        "product_name": "San pham Demo A",
                        "product_description": "Mo ta san pham demo A cua Member Two.",
                        "price": None,
                        "color_theme": None,
                        "facebook_url": None,
                        "tiktok_url": None,
                        "instagram_url": None,
                        "status": "draft",
                    },
                    {
                        "user_id": member2_id,
                        "template_id": 2,
                        "campaign_name": "Demo cua Member Two B",
                        "product_name": "San pham Demo B",
                        "product_description": "Mo ta san pham demo B cua Member Two.",
                        "price": None,
                        "color_theme": None,
                        "facebook_url": None,
                        "tiktok_url": None,
                        "instagram_url": None,
                        "status": "draft",
                    },
                ]

                for p in demo_projects:
                    cursor.execute(
                        "SELECT id FROM projects WHERE user_id = %s AND campaign_name = %s;",
                        (p["user_id"], p["campaign_name"]),
                    )
                    existing = cursor.fetchone()
                    if not existing:
                        cursor.execute(
                            """
                            INSERT INTO projects (
                                user_id, template_id, campaign_name, product_name, product_description,
                                price, color_theme, facebook_url, tiktok_url, instagram_url, status
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                            """,
                            (
                                p["user_id"],
                                p["template_id"],
                                p["campaign_name"],
                                p["product_name"],
                                p["product_description"],
                                p["price"],
                                p["color_theme"],
                                p["facebook_url"],
                                p["tiktok_url"],
                                p["instagram_url"],
                                p["status"],
                            ),
                        )
                        project_id = cursor.lastrowid
                        created += 1
                    else:
                        project_id = existing[0]

                    if p["status"] == "published":
                        cursor.execute(
                            "SELECT COUNT(*) FROM deployments WHERE project_id = %s AND commit_sha = %s;",
                            (project_id, "demo0001"),
                        )
                        if cursor.fetchone()[0] == 0:
                            cursor.execute(
                                """
                                INSERT INTO deployments (project_id, commit_sha, status, error_message, start_time, end_time)
                                VALUES (%s, %s, %s, %s, NOW() - INTERVAL 2 DAY, NOW() - INTERVAL 2 DAY);
                                """,
                                (project_id, "demo0001", "Failed", "Mau: loi push len GitHub"),
                            )

                        cursor.execute(
                            "SELECT COUNT(*) FROM deployments WHERE project_id = %s AND commit_sha = %s;",
                            (project_id, "demo0002"),
                        )
                        if cursor.fetchone()[0] == 0:
                            cursor.execute(
                                """
                                INSERT INTO deployments (project_id, commit_sha, status, error_message, start_time, end_time)
                                VALUES (%s, %s, %s, %s, NOW() - INTERVAL 1 DAY, NOW() - INTERVAL 1 DAY);
                                """,
                                (project_id, "demo0002", "Success", None),
                            )

            print(f"Seeded {created} demo projects.")
            print("Database migration & seeding completed successfully!")

    except Exception as e:
        print(f"Error initializing database: {e}")
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    init_database()