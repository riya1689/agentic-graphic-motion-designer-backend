# Agentic Graphic and Motion Designer

An enterprise-grade, modular, agentic AI workspace for creating editable graphic assets (Adobe Illustrator, Photoshop) and motion sequences (After Effects).

## Modules Architecture
- `core/`: Shared configurations and API authentication gateway.
- `packages/prompt_to_json_agent/`: Dedicated prompt extraction, requirement coverage verification, gap detection, and zero-null validation engine.
- `packages/planner_agent/`: Technical layer blueprint & coordinate calculation planner.
- `packages/graphic_agent/`: Adobe Illustrator / Photoshop ExtendScript & vector generator.
- `packages/motion_agent/`: Motion sequence & animation generator.
- `packages/manager_agent/`: Central orchestrator state-machine.