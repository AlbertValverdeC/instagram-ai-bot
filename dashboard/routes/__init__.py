from __future__ import annotations

from flask import Flask

from dashboard.routes.keys import bp as keys_bp
from dashboard.routes.pipeline import bp as pipeline_bp
from dashboard.routes.posts import bp as posts_bp
from dashboard.routes.prompts import bp as prompts_bp
from dashboard.routes.research import bp as research_bp


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(pipeline_bp)
    app.register_blueprint(keys_bp)
    app.register_blueprint(prompts_bp)
    app.register_blueprint(research_bp)
    app.register_blueprint(posts_bp)
