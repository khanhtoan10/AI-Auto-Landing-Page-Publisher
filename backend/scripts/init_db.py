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
            print("Database migration & seeding completed successfully!")

    except Exception as e:
        print(f"Error initializing database: {e}")
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    init_database()