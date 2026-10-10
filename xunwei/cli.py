import click
from datetime import datetime
from werkzeug.security import generate_password_hash
from .db import get_db, init_db
from .migrations import backup_database


def register_commands(app):
    @app.cli.command('init-db')
    @click.option('--demo', is_flag=True, help='Initialize a NEW demo database with sample accounts.')
    def initialize(demo):
        """Create or upgrade tables, keeping existing data."""
        if demo and app.config['PRODUCTION']:
            raise click.ClickException('Demo data is disabled in production.')
        previous = app.config['SEED_DEMO']
        try:
            app.config['SEED_DEMO'] = demo
            init_db()
        finally:
            app.config['SEED_DEMO'] = previous
        click.echo('Database ready.')

    @app.cli.command('create-admin')
    @click.option('--username', prompt=True)
    @click.password_option()
    def create_admin(username, password):
        """Create an administrator without a hard-coded initial password."""
        username = username.strip()
        if not 3 <= len(username) <= 20 or not 8 <= len(password) <= 72:
            raise click.ClickException('Username: 3-20 characters; password: 8-72 characters.')
        init_db()
        db = get_db()
        if db.execute('SELECT 1 FROM users WHERE username=?', (username,)).fetchone():
            raise click.ClickException('Username already exists.')
        db.execute('INSERT INTO users(username,password_hash,role,created_at) VALUES (?,?,?,?)',
                   (username, generate_password_hash(password), 'admin', datetime.now().isoformat(timespec='seconds')))
        db.commit()
        click.echo('Administrator created.')

    @app.cli.command('backup-db')
    def backup():
        """Create a consistent SQLite backup without stopping the application."""
        click.echo(str(backup_database(get_db())))
