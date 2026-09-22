source venv/bin/activate
# Which Flow project to scope RPCs to. Put the uuid in .flow_project_id, or
# export FLOW_PROJECT_ID before running. Unpinned, media lookups fall back to a
# per-process cache and fail whenever it misses.
if [ -z "$FLOW_PROJECT_ID" ] && [ -f .flow_project_id ]; then
  export FLOW_PROJECT_ID="$(tr -d '[:space:]' < .flow_project_id)"
fi
export VIDEO_POLL_TIMEOUT="${VIDEO_POLL_TIMEOUT:-900}"
# OmniVoice lives in this venv, not the python3.10 the TTS service defaults to.
export TTS_PYTHON_BIN="${TTS_PYTHON_BIN:-$PWD/venv/bin/python}"
python -m agent.main

