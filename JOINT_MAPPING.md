# 关节映射说明（仿真 vs 前端一致）

本仓库里存在**两种关节顺序**，用途不同；**3D 画面（你看到的）只由「仿真」驱动，与 policy 顺序一致**。

---

## 1. 两种顺序分别是什么、用在哪

| 顺序 | 定义位置 | 用途 |
|------|----------|------|
| **policy 顺序** | `public/examples/checkpoints/g1/tracking_policy_*.json` 里的 `policy_joint_names` | 仿真：策略输出 action 按此顺序写入 MuJoCo；`readPolicyState()` 读出的 `jointPos` 也是此顺序。**你在网页里看到的人体动作就是按这个顺序控制的。** |
| **dataset 顺序** | 同上 JSON 里 `tracking.dataset_joint_names` | 仅用于 **TrackingHelper 的 ref**：参考动作 `refJointPos`、策略观测 TargetJointPosObs 等都以 dataset 顺序输入策略。与 motions.json / 训练数据顺序一致。 |

两种顺序的**关节名称集合相同**，只是**下标顺序不同**（例如 policy 是左右交替，dataset 常为左腿→右腿→腰→左臂→右臂等）。

---

## 2. 涉及关节映射的代码位置

- **仿真：用 policy 顺序写/读**
  - `src/simulation/mujocoUtils.js`  
    - `configureJointMappings(demo, jointNames)`：用 `policy_joint_names` 建 `qpos_adr_policy` / `ctrl_adr_policy`，把「policy 下标 i」映射到 MuJoCo 的关节。
  - `src/simulation/main.js`  
    - `main_loop()`：`actionTarget[i]` 写到 `qpos_adr_policy[i]`（即 policy 顺序）。  
    - `readPolicyState()`：从 `qpos_adr_policy[i]` 读出 `jointPos[i]`（policy 顺序）。

- **Tracking：ref 用 dataset 顺序**
  - `src/simulation/trackingHelper.js`  
    - `datasetJointNames` / `policyJointNames` 来自 config。  
    - `_buildPolicyToDatasetMap()`、`_mapPolicyJointPosToDataset()`、`convertMotionJointPosPolicyToDataset()`：在 **policy 顺序 ↔ dataset 顺序** 之间转换。  
    - `_startMotionFromCurrent()` 里：当前状态 `state.jointPos` 是 policy 顺序，会转成 dataset 再与 motion 做过渡。  
    - 内部存的 motion 和 `refJointPos` 均为 **dataset 顺序**，供观测输入策略。

- **前端：API 动作写入 Tracking**
  - `src/views/Demo.vue` 的 `addMotionToTracking(motionData)`  
    - 后端（text_motion_api）返回的 `joint_pos` 注释为 **Isaac / policy 顺序**。  
    - 这里会先转成 **dataset 顺序** 再交给 TrackingHelper，这样 ref 与策略训练时一致，**仿真展示（policy 顺序控制）才会正确**。

---

## 3. 前端「展示」和仿真是否一致

- **网页上看到的 3D 动作**：完全由 **MuJoCo 仿真** 驱动，控制量按 **policy 顺序** 写入（见上）。没有另一套「前端自己的关节映射」在画图。
- 因此：**只要 ref 是 dataset 顺序（由上面转换保证），策略输入/输出和仿真用的顺序关系就一致，前端展示与仿真一致。**

若发现动作错位，请检查：  
1）后端返回的 `joint_pos` 是否确认为 **policy（Isaac）顺序**；  
2）若后端实际改为 **dataset 顺序** 输出，则需在 `addMotionToTracking` 中**不做** `convertMotionJointPosPolicyToDataset`，直接使用 `motionData.joint_pos`。

---

## 4. 发布前端

在项目根目录执行：

```bash
bash publish_frontend.sh
```

需已设置环境变量 `GITHUB_TOKEN`（及可选 `GITHUB_USER`、`GITHUB_REPO`）。脚本会构建、提交并推送到配置的 GitHub 仓库，由 GitHub Actions 部署到 GitHub Pages。详见脚本内注释和 `DEPLOY_README.md`。
