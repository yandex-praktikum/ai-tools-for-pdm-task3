from flask import Flask, render_template, request

from studio_shift.agent_runtime import AgentRuntimeError, run_agent
from studio_shift.store import initialize_store, list_all_tasks, list_recent_traces


app = Flask(__name__)
app.secret_key = "studio-shift-local-session"


def render_dashboard(agent_result=None):
    tasks = list_all_tasks()
    open_tasks = [task for task in tasks if task["status"] == "open"]
    completed_tasks = [task for task in tasks if task["status"] == "done"]
    high_priority_count = sum(
        task["priority"] == "Высокий" for task in open_tasks
    )
    return render_template(
        "index.html",
        open_tasks=open_tasks,
        completed_tasks=completed_tasks,
        high_priority_count=high_priority_count,
        agent_result=agent_result,
        traces=list_recent_traces(limit=8),
    )


@app.before_request
def prepare_local_store():
    initialize_store()


@app.get("/")
def index():
    return render_dashboard()


@app.post("/agent")
def agent_command():
    command = request.form.get("command", "").strip()
    if not command:
        return render_dashboard(
            {
                "title": "Нужна команда",
                "message": "Опишите действие для координатора.",
            }
        )

    try:
        result = run_agent(command)
    except AgentRuntimeError as exc:
        result = {
            "title": "Команда не завершена",
            "message": str(exc),
        }
    return render_dashboard(agent_result=result)


if __name__ == "__main__":
    app.run(host="127.0.0.2", port=5000, debug=False)
