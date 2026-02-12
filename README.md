# SHELL: Semantic Hierarchical Embodied Language-to-Motion with Low-level Tracking

Browser-based demo for language-conditioned humanoid whole-body control. The app runs a MuJoCo WebAssembly scene driven by an ONNX tracking policy and connects to a text-to-motion backend for language-driven motion generation.

## Overview

Natural language is an appealing interface for humanoid robots: it is expressive and describes goals and constraints directly. This project implements a deployment-oriented **edge–cloud** setup: a diffusion-based text-to-motion generator produces **robot-native** motion references on the server, while a lightweight tracking controller runs in the browser (and can run on-robot) in closed loop. The motion representation is a compact **38D velocity-based** format (joint positions, root velocity, height, and rotation) that is retargeting-free and tracker-friendly, bridging generative planning and real-time execution. The system is validated in simulation and on real hardware.

**Main contributions:**
- Edge–cloud language-to-humanoid control with streaming motion references and on-board tracking.
- Robot-native 38D motion interface: retargeting-free, streamable, and compatible with receding-horizon trackers.
- Evaluations in simulation and on a real humanoid robot.

## Quick start

```bash
npm install
npm run dev
```

The default setup loads the G1 scene, ONNX policy, and motion clips from `public/examples`. Configure the text-to-motion API URL via environment (e.g. `VITE_TEXT_MOTION_API_URL` for the frontend; see `text_motion_api/.env.example` for the gateway).

## Project structure

| Path | Description |
|------|-------------|
| `src/views/Demo.vue` | Main UI: simulation controls, text-to-motion panel, shortcuts |
| `src/simulation/main.js` | MuJoCo + Three.js + policy loop bootstrap |
| `src/simulation/policyRunner.js` | ONNX inference and tracking pipeline |
| `src/simulation/trackingHelper.js` | Motion playback and policy/dataset joint order mapping |
| `text_motion_api/` | FastAPI gateway: sessions, rate limits, proxy to motion generation backend |
| `public/examples/` | Scenes (MJCF), checkpoints (policy JSON + ONNX), motion clips |

## Adding a robot or policy

1. **Scene:** Add MJCF and assets under `public/examples/scenes/<robot>/`, and list paths in `public/examples/scenes/files.json`.
2. **Policy:** Add `tracking_policy.json` and the ONNX under `public/examples/checkpoints/<robot>/`. Ensure `policy_joint_names` and `obs_config` match your MJCF and `observationHelpers.js`.
3. **Motions (optional):** Add `motions.json` and clip files; set `tracking.motions_path` in the policy JSON.

Joint order: the policy uses `policy_joint_names` for simulation I/O; tracking references use `dataset_joint_names` (see policy JSON). The viewer converts between them in `trackingHelper.js`.

## Configuration

- **Frontend:** Set `VITE_TEXT_MOTION_API_URL` (and optionally `VITE_API_KEY`) at build time for the text-to-motion gateway.
- **Gateway:** See `text_motion_api/.env.example` for `REMOTE_WS_*`, rate limits, CORS origins, and optional API key. Run the gateway with `uvicorn main:app` or the provided scripts.

## License

See repository for license and attribution.
