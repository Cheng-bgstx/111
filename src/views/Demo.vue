<template>
  <div id="mujoco-container"></div>
  <div class="global-alerts">
    <v-alert
      v-if="isSmallScreen && showSmallScreenAlert"
      type="info"
      variant="flat"
      density="compact"
      closable
      class="small-screen-alert"
      @click:close="showSmallScreenAlert = false"
    >
      手机版：下方为控制面板，可输入文本指令或使用快捷命令操作。
    </v-alert>
    <v-alert
      v-if="isSafari"
      v-model="showSafariAlert"
      type="warning"
      variant="flat"
      density="compact"
      closable
      class="safari-alert"
    >
      Safari has lower memory limits, which can cause WASM to crash.
    </v-alert>
  </div>
  <div class="controls" :class="{ 'controls--mobile': isSmallScreen }">
    <v-card class="controls-card">
      <v-card-title class="controls-title">文本生成动作</v-card-title>
      <v-card-text class="py-0 controls-body">
        <!-- 使用说明 -->
        <section class="usage-instructions">
          <h3 class="usage-heading">文本生成动作工具</h3>
          <p class="usage-desc">输入文本描述 → 生成并加载动作</p>
          <ul class="usage-bullets">
            <li>动作执行中可随时输入新文本切换动作</li>
            <li>动作完成后自动切换到 default 姿态</li>
          </ul>
          <div class="usage-cmds">
            <span class="usage-cmds-label">命令</span>
            <div class="usage-cmd-row"><kbd>&lt;文本描述&gt;</kbd> 生成新动作</div>
            <div class="usage-cmd-row"><kbd>default</kbd> 手动回到默认姿态</div>
            <div class="usage-cmd-row"><kbd>up</kbd> 站起并自动恢复（摔倒后使用）</div>
            <div class="usage-cmd-row"><kbd>last</kbd> 重新加载上一个生成的动作</div>
            <div class="usage-cmd-row"><kbd>list</kbd> 显示所有已生成的动作</div>
            <div class="usage-cmd-row"><kbd>clear</kbd> 清理当前会话下的生成动作</div>
            <div class="usage-cmd-row"><kbd>status</kbd> 显示当前动作状态</div>
            <div class="usage-cmd-row"><kbd>q</kbd>/<kbd>quit</kbd> 退出（网页请直接关闭页面）</div>
          </div>
        </section>
        <div class="section-divider"></div>

        <!-- 快捷命令 -->
        <section class="command-section">
          <span class="section-label">快捷命令</span>
          <div class="command-buttons">
            <v-btn size="x-small" variant="tonal" color="primary" :disabled="state !== 1" @click="backToDefault">default</v-btn>
            <v-btn size="x-small" variant="tonal" color="primary" :disabled="state !== 1 || !hasUpMotion" @click="runUpStand">up</v-btn>
            <v-btn size="x-small" variant="tonal" color="primary" :disabled="state !== 1 || !lastGeneratedMotion" @click="replayLastMotion">last</v-btn>
            <v-btn size="x-small" variant="tonal" color="primary" :disabled="state !== 1" @click="listGeneratedMotions">list</v-btn>
            <v-btn size="x-small" variant="tonal" color="primary" :disabled="state !== 1" @click="showStatus">status</v-btn>
            <v-btn size="x-small" variant="tonal" color="primary" :disabled="state !== 1" @click="clearOldMotions">clear</v-btn>
          </div>
        </section>
        <div class="section-divider"></div>

        <!-- Text-to-Motion Section -->
        <section class="text-to-motion-section">
          <span class="section-label">AI 动作生成</span>
          <div class="status-legend">
            <v-chip
              v-if="textMotionStatus === 'connected'"
              size="x-small"
              color="success"
              variant="flat"
            >
              <v-icon icon="mdi-check-circle" size="x-small" class="mr-1"></v-icon>
              Ready
            </v-chip>
            <v-chip
              v-else-if="textMotionStatus === 'generating'"
              size="x-small"
              color="warning"
              variant="flat"
            >
              <v-icon icon="mdi-loading" size="x-small" class="mr-1 spinning"></v-icon>
              Generating...
            </v-chip>
            <v-chip
              v-else-if="textMotionStatus === 'error'"
              size="x-small"
              color="error"
              variant="flat"
            >
              <v-icon icon="mdi-alert" size="x-small" class="mr-1"></v-icon>
              Error
            </v-chip>
            <v-chip
              v-else
              size="x-small"
              color="grey"
              variant="flat"
            >
              <v-icon icon="mdi-minus-circle" size="x-small" class="mr-1"></v-icon>
              Not Connected
            </v-chip>
          </div>

          <v-expand-transition>
            <div v-if="showTextMotionPanel">
              <v-textarea
                v-model="textPrompt"
                label="输入文本描述"
                placeholder="例如: a person walks forward"
                density="compact"
                hide-details
                rows="2"
                class="mt-2"
                :disabled="state !== 1 || textMotionStatus === 'generating'"
                @keydown.enter.prevent="handleEnterKey"
              ></v-textarea>
              <div class="example-prompts mt-2">
                <span class="text-caption mr-1">示例（点击即生成）:</span>
                <div class="example-chips">
                  <v-chip
                    v-for="ex in examplePrompts"
                    :key="ex"
                    size="x-small"
                    variant="tonal"
                    class="example-chip"
                    :disabled="state !== 1 || textMotionStatus === 'generating'"
                    @click="runExample(ex)"
                  >
                    {{ ex }}
                  </v-chip>
                </div>
              </div>

              <v-expand-transition>
                <div v-if="showAdvancedOptions" class="advanced-options mt-2">
                  <v-row dense>
                    <v-col cols="6">
                      <v-text-field
                        v-model.number="motionLength"
                        label="Duration (s)"
                        type="number"
                        min="0.1"
                        max="9"
                        step="0.1"
                        density="compact"
                        hide-details
                        :disabled="state !== 1 || textMotionStatus === 'generating'"
                      ></v-text-field>
                    </v-col>
                    <v-col cols="6">
                      <v-text-field
                        v-model.number="inferenceSteps"
                        label="Quality Steps"
                        type="number"
                        min="1"
                        max="100"
                        step="1"
                        density="compact"
                        hide-details
                        :disabled="state !== 1 || textMotionStatus === 'generating'"
                      ></v-text-field>
                    </v-col>
                  </v-row>
                  <v-row dense class="mt-2">
                    <v-col cols="6">
                      <v-text-field
                        v-model.number="transitionSteps"
                        label="Transition Steps"
                        type="number"
                        min="0"
                        max="300"
                        step="10"
                        density="compact"
                        hide-details
                        :disabled="state !== 1 || textMotionStatus === 'generating'"
                      ></v-text-field>
                    </v-col>
                    <v-col cols="6">
                      <v-switch
                        v-model="adaptiveSmooth"
                        label="Smooth Motion"
                        density="compact"
                        hide-details
                        :disabled="state !== 1 || textMotionStatus === 'generating'"
                      ></v-switch>
                    </v-col>
                  </v-row>
                </div>
              </v-expand-transition>

              <div class="d-flex align-center mt-2">
                <v-btn
                  color="primary"
                  size="small"
                  :loading="textMotionStatus === 'generating'"
                  :disabled="!canGenerateMotion"
                  @click="generateMotionFromText"
                  class="flex-grow-1"
                >
                  <v-icon icon="mdi-send" class="mr-1"></v-icon>
                  Generate
                </v-btn>
                <v-btn
                  variant="text"
                  size="small"
                  density="compact"
                  @click="showAdvancedOptions = !showAdvancedOptions"
                >
                  <v-icon :icon="showAdvancedOptions ? 'mdi-chevron-up' : 'mdi-chevron-down'"></v-icon>
                </v-btn>
              </div>

              <v-alert
                v-if="textMotionError"
                type="error"
                variant="tonal"
                density="compact"
                class="mt-2"
                closable
                @click:close="textMotionError = ''"
              >
                {{ textMotionError }}
              </v-alert>

              <v-alert
                v-if="textMotionSuccess"
                type="success"
                variant="tonal"
                density="compact"
                class="mt-2"
                closable
                @click:close="textMotionSuccess = ''"
              >
                {{ textMotionSuccess }}
              </v-alert>
            </div>
          </v-expand-transition>

          <v-btn
            v-if="!showTextMotionPanel"
            variant="text"
            density="compact"
            color="primary"
            class="mt-2"
            @click="showTextMotionPanel = true"
          >
            <v-icon icon="mdi-robot" class="mr-1"></v-icon>
            Generate motions with AI
          </v-btn>
        </section>

        <v-divider class="my-2"/>

        <!-- list: 已生成的动作（最多 10 个） -->
        <div v-if="generatedMotions.length > 0" class="generated-section mt-2">
          <span class="section-label">已生成的动作</span>
          <div class="status-legend generated-legend">
            <v-chip size="x-small" variant="tonal" color="primary">{{ generatedMotions.length }}/10{{ generatedMotions.length >= 10 ? '（已达上限）' : '' }}</v-chip>
          </div>
          <p class="generated-hint">最多保留 10 个，点击可重新播放。</p>
          <div class="generated-motions-list">
            <v-chip
              v-for="motion in generatedMotions"
              :key="motion.motion_id"
              :color="currentMotion === motion.motion_id ? 'primary' : undefined"
              :variant="currentMotion === motion.motion_id ? 'flat' : 'tonal'"
              size="x-small"
              class="motion-chip"
              @click="playGeneratedMotion(motion)"
            >
              <v-icon icon="mdi-play-circle" size="x-small" class="mr-1"></v-icon>
              {{ motion.text_prompt || motion.motion_id }}
            </v-chip>
          </div>
          <v-divider class="my-2"/>
        </div>

        <!-- status 显示 -->
        <div v-if="statusMessage" class="status-message text-caption mt-2">{{ statusMessage }}</div>
      </v-card-text>
      <v-card-actions>
        <v-btn color="primary" block @click="reset">Reset</v-btn>
      </v-card-actions>
    </v-card>
  </div>
  <v-dialog :model-value="state === 0" persistent max-width="600px" scrollable>
    <v-card title="Loading Simulation Environment">
      <v-card-text>
        <v-progress-linear indeterminate color="primary"></v-progress-linear>
        Loading MuJoCo and ONNX policy, please wait
      </v-card-text>
    </v-card>
  </v-dialog>
  <v-dialog :model-value="state < 0" persistent max-width="600px" scrollable>
    <v-card title="Simulation Environment Loading Error">
      <v-card-text>
        <span v-if="state === -1">
          Unexpected runtime error, please refresh the page.<br />
          {{ extra_error_message }}
        </span>
        <span v-else-if="state === -2">
          Your browser does not support WebAssembly. Please use a recent version of Chrome, Edge, or Firefox.
        </span>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script>
import { MuJoCoDemo } from '@/simulation/main.js';
import loadMujoco from 'mujoco-js';

// Text-to-Motion API configuration
const TEXT_MOTION_API_URL = import.meta.env.VITE_TEXT_MOTION_API_URL || 'http://localhost:8080';
const SESSION_STORAGE_KEY = 'text_motion_session_id';
const MAX_GENERATED_MOTIONS = 10;

export default {
  name: 'DemoPage',
  data: () => ({
    state: 0, // 0: loading, 1: running, -1: JS error, -2: wasm unsupported
    extra_error_message: '',
    keydown_listener: null,
    currentMotion: null,
    availableMotions: [],
    trackingState: {
      available: false,
      currentName: 'default',
      currentDone: true,
      refIdx: 0,
      refLen: 0,
      transitionLen: 0,
      motionLen: 0,
      inTransition: false,
      isDefault: true
    },
    trackingTimer: null,
    policies: [
      {
        value: 'g1-tracking-lafan',
        title: 'G1 Tracking (LaFan1)',
        description: 'General tracking policy trained on LaFan1 dataset.',
        policyPath: './examples/checkpoints/g1/tracking_policy_lafan.json',
        onnxPath: './examples/checkpoints/g1/policy_lafan.onnx'
      },
      {
        value: 'g1-tracking-lafan_amass',
        title: 'G1 Tracking (LaFan1&AMASS)',
        description: 'General tracking policy trained on LaFan1 and AMASS datasets.',
        policyPath: './examples/checkpoints/g1/tracking_policy_amass.json',
        onnxPath: './examples/checkpoints/g1/policy_amass.onnx'
      }
    ],
    currentPolicy: 'g1-tracking-lafan_amass',
    policyLabel: '',
    isPolicyLoading: false,
    policyLoadError: '',
    motionUploadFiles: [],
    motionUploadMessage: '',
    motionUploadType: 'success',
    showUploadOptions: false,
    cameraFollowEnabled: true,
    renderScale: 2.0,
    simStepHz: 0,
    isSmallScreen: false,
    showSmallScreenAlert: true,
    isSafari: false,
    showSafariAlert: true,
    resize_listener: null,
    // Text-to-Motion related data
    sessionId: null,
    sessionStorageKey: SESSION_STORAGE_KEY,
    textPrompt: '',
    showTextMotionPanel: false,
    showAdvancedOptions: false,
    textMotionStatus: 'disconnected', // 'disconnected', 'connected', 'generating', 'error'
    textMotionError: '',
    textMotionSuccess: '',
    motionLength: 4.0,
    inferenceSteps: 10,
    transitionSteps: 100,
    adaptiveSmooth: true,
    generatedMotions: [],
    generatedMotionMap: new Map(),
    lastGeneratedMotion: null,
    statusMessage: '',
    autoDefaultTriggered: false,
    isUprightMonitoring: false,
    uprightCheckCount: 0,
    UPRIGHT_CONSECUTIVE_FRAMES: 8,
    examplePrompts: [
      'a person is jogging on the spot',
      'person is boxing, they throw an upper cut then defend and dodge then they throw a few right jabs',
      'a person side steps to the right and then to the left, and back to the middle',
      'walk in a circle',
      'jump jacks'
    ]
  }),
  computed: {
    shouldShowProgress() {
      const state = this.trackingState;
      if (!state || !state.available) {
        return false;
      }
      if (state.refLen > 1) {
        return true;
      }
      return !state.currentDone || !state.isDefault || state.inTransition;
    },
    progressValue() {
      const state = this.trackingState;
      if (!state || state.refLen <= 0) {
        return 0;
      }
      const value = ((state.refIdx + 1) / state.refLen) * 100;
      return Math.max(0, Math.min(100, value));
    },
    showBackToDefault() {
      const state = this.trackingState;
      return state && state.available && !state.isDefault && state.currentDone;
    },
    showMotionLockedNotice() {
      const state = this.trackingState;
      return state && state.available && !state.isDefault && !state.currentDone;
    },
    showMotionSelect() {
      const state = this.trackingState;
      if (!state || !state.available) {
        return false;
      }
      if (!state.isDefault || !state.currentDone) {
        return false;
      }
      return this.motionItems.some((item) => !item.disabled);
    },
    motionItems() {
      const names = [...this.availableMotions].sort((a, b) => {
        if (a === 'default') {
          return -1;
        }
        if (b === 'default') {
          return 1;
        }
        return a.localeCompare(b);
      });
      return names.map((name) => ({
        title: name.split('_')[0],
        value: name,
        disabled: name === 'default'
      }));
    },
    motionGroups() {
      const items = this.motionItems.filter((item) => item.value !== 'default');
      if (items.length === 0) {
        return [];
      }
      const customized = [];
      const amass = [];
      const lafan = [];

      for (const item of items) {
        const value = item.value.toLowerCase();
        if (value.includes('[new]')) {
          customized.push(item);
        } else if (value.includes('amass')) {
          amass.push(item);
        } else {
          lafan.push(item);
        }
      }

      const groups = [];
      if (lafan.length > 0) {
        groups.push({ title: 'LAFAN1', items: lafan });
      }
      if (amass.length > 0) {
        groups.push({ title: 'AMASS', items: amass });
      }
      if (customized.length > 0) {
        groups.push({ title: 'Customized', items: customized });
      }
      return groups;
    },
    policyItems() {
      return this.policies.map((policy) => ({
        title: policy.title,
        value: policy.value
      }));
    },
    selectedPolicy() {
      return this.policies.find((policy) => policy.value === this.currentPolicy) ?? null;
    },
    policyDescription() {
      return this.selectedPolicy?.description ?? '';
    },
    renderScaleLabel() {
      return `${this.renderScale.toFixed(2)}x`;
    },
    simStepLabel() {
      if (!this.simStepHz || !Number.isFinite(this.simStepHz)) {
        return '—';
      }
      return `${this.simStepHz.toFixed(1)} Hz`;
    },
    canGenerateMotion() {
      return this.state === 1 &&
             this.textPrompt.trim().length > 0 &&
             this.textMotionStatus !== 'generating';
    },
    canSelectGeneratedMotion() {
      return this.state === 1 && this.demo?.policyRunner?.tracking;
    },
    hasUpMotion() {
      const list = this.getAvailableMotions();
      return list.includes('fallAndGetUp2_subject2') || list.includes('fallAndGetUp1_subject1');
    }
  },
  methods: {
    detectSafari() {
      const ua = navigator.userAgent;
      return /Safari\//.test(ua)
        && !/Chrome\//.test(ua)
        && !/Chromium\//.test(ua)
        && !/Edg\//.test(ua)
        && !/OPR\//.test(ua)
        && !/SamsungBrowser\//.test(ua)
        && !/CriOS\//.test(ua)
        && !/FxiOS\//.test(ua);
    },
    updateScreenState() {
      const isSmall = window.innerWidth < 500 || window.innerHeight < 700;
      if (!isSmall && this.isSmallScreen) {
        this.showSmallScreenAlert = true;
      }
      this.isSmallScreen = isSmall;
    },
    async init() {
      if (typeof WebAssembly !== 'object' || typeof WebAssembly.instantiate !== 'function') {
        this.state = -2;
        return;
      }

      try {
        const mujoco = await loadMujoco();
        this.demo = new MuJoCoDemo(mujoco);
        this.demo.setFollowEnabled?.(this.cameraFollowEnabled);
        await this.demo.init();
        this.demo.main_loop();
        this.demo.params.paused = false;
        this.reapplyCustomMotions();
        this.availableMotions = this.getAvailableMotions();
        this.currentMotion = this.demo.params.current_motion ?? this.availableMotions[0] ?? null;
        this.startTrackingPoll();
        this.renderScale = this.demo.renderScale ?? this.renderScale;
        const matchingPolicy = this.policies.find(
          (policy) => policy.policyPath === this.demo.currentPolicyPath
        );
        if (matchingPolicy) {
          this.currentPolicy = matchingPolicy.value;
        }
        this.policyLabel = this.demo.currentPolicyPath?.split('/').pop() ?? this.policyLabel;

        // Initialize text-to-motion session
        await this.initTextMotionSession();

        this.state = 1;
      } catch (error) {
        this.state = -1;
        this.extra_error_message = error.toString();
        console.error(error);
      }
    },

    // ==================== Text-to-Motion Methods ====================

    buildSessionHeaders(includeContentType = false) {
      const headers = {};
      if (includeContentType) {
        headers['Content-Type'] = 'application/json';
      }
      if (this.sessionId) {
        headers['X-Session-ID'] = this.sessionId;
      }
      return headers;
    },

    /** 服务端返回 403 SESSION_FORBIDDEN 时清除本地会话并提示（如更换设备/网络导致） */
    clearSessionForbidden() {
      this.sessionId = null;
      try {
        sessionStorage.removeItem(this.sessionStorageKey);
      } catch (e) {}
      this.textMotionStatus = 'disconnected';
      this.statusMessage = '会话已失效（如更换设备或网络），已自动清除，请重试。';
      setTimeout(() => { this.statusMessage = ''; }, 5000);
    },

    async initTextMotionSession() {
      // Initialize or resume session with the text-to-motion API
      try {
        const stored = sessionStorage.getItem(this.sessionStorageKey);
        if (stored) {
          this.sessionId = stored;
        }
        const response = await fetch(`${TEXT_MOTION_API_URL}/api/session`, {
          method: 'POST',
          headers: this.buildSessionHeaders(true)
        });

        if (response.ok) {
          const data = await response.json();
          this.sessionId = data.session_id;
          sessionStorage.setItem(this.sessionStorageKey, this.sessionId);
          this.textMotionStatus = 'connected';
          console.log('[TextMotion] Session created:', this.sessionId);
          await this.loadGeneratedMotionsFromServer();
          return;
        }
        if (response.status === 403) {
          const errData = await response.json().catch(() => ({}));
          if (errData.code === 'SESSION_FORBIDDEN') {
            this.sessionId = null;
            try { sessionStorage.removeItem(this.sessionStorageKey); } catch (e) {}
            const retryRes = await fetch(`${TEXT_MOTION_API_URL}/api/session`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' }
            });
            if (retryRes.ok) {
              const data = await retryRes.json();
              this.sessionId = data.session_id;
              sessionStorage.setItem(this.sessionStorageKey, this.sessionId);
              this.textMotionStatus = 'connected';
              this.statusMessage = '已自动创建新会话，请继续使用。';
              setTimeout(() => { this.statusMessage = ''; }, 4000);
              await this.loadGeneratedMotionsFromServer();
              return;
            }
          }
        }
        console.warn('[TextMotion] Failed to create session');
        this.textMotionStatus = 'disconnected';
      } catch (error) {
        console.warn('[TextMotion] API not available:', error.message);
        this.textMotionStatus = 'disconnected';
      }
    },

    handleEnterKey(event) {
      // Handle Enter key in text area - generate if Shift is not pressed
      if (!event.shiftKey && this.canGenerateMotion) {
        this.generateMotionFromText();
      }
    },

    async handleTextCommand(prompt) {
      const cmd = prompt.trim().toLowerCase();
      if (!cmd) {
        return false;
      }
      if (cmd === 'default') {
        this.backToDefault();
        this.statusMessage = '已切换到 default。';
        return true;
      }
      if (cmd === 'up' || cmd === 'u') {
        this.runUpStand();
        return true;
      }
      if (cmd === 'last') {
        this.replayLastMotion();
        this.statusMessage = this.lastGeneratedMotion ? '已加载上一个生成动作。' : '暂无上一个生成动作。';
        return true;
      }
      if (cmd === 'list') {
        this.listGeneratedMotions();
        return true;
      }
      if (cmd === 'clear') {
        await this.clearOldMotions();
        return true;
      }
      if (cmd === 'status') {
        this.showStatus();
        return true;
      }
      if (cmd === 'q' || cmd === 'quit') {
        this.statusMessage = '网页模式无需 quit，请直接关闭页面标签。';
        setTimeout(() => { this.statusMessage = ''; }, 4000);
        return true;
      }
      return false;
    },

    async loadGeneratedMotionsFromServer() {
      if (!this.sessionId) {
        return;
      }
      try {
        const listResp = await fetch(`${TEXT_MOTION_API_URL}/api/motions`, {
          method: 'GET',
          headers: this.buildSessionHeaders(false)
        });
        if (!listResp.ok) {
          if (listResp.status === 403) {
            const d = await listResp.json().catch(() => ({}));
            if (d.code === 'SESSION_FORBIDDEN') this.clearSessionForbidden();
          }
          return;
        }
        const payload = await listResp.json();
        const items = Array.isArray(payload.motions) ? payload.motions : [];
        if (items.length === 0) {
          return;
        }

        const fetched = [];
        for (const item of items) {
          const motionId = item.motion_id;
          if (!motionId) {
            continue;
          }
          const motionResp = await fetch(`${TEXT_MOTION_API_URL}/api/motions/${motionId}`, {
            method: 'GET',
            headers: this.buildSessionHeaders(false)
          });
          if (!motionResp.ok) {
            if (motionResp.status === 403) {
              const d = await motionResp.json().catch(() => ({}));
              if (d.code === 'SESSION_FORBIDDEN') this.clearSessionForbidden();
            }
            continue;
          }
          const motionData = await motionResp.json();
          fetched.push({
            ...motionData,
            motion_id: motionId,
            text_prompt: item.text_prompt ?? motionData.text_prompt ?? ''
          });
        }

        fetched.sort((a, b) => (a.created_at || '').localeCompare(b.created_at || ''));
        for (const motionData of fetched) {
          this.generatedMotionMap.set(motionData.motion_id, motionData);
          this.addMotionToTracking(motionData);
        }
        await this.trimGeneratedMotions(MAX_GENERATED_MOTIONS);
        this.generatedMotions = Array.from(this.generatedMotionMap.values());
        if (this.generatedMotions.length > 0) {
          this.lastGeneratedMotion = this.generatedMotions[this.generatedMotions.length - 1];
        }
      } catch (error) {
        console.warn('[TextMotion] Failed to restore motions:', error.message);
      }
    },

    async generateMotionFromText() {
      // Generate motion from text description
      if (!this.canGenerateMotion) return;

      const prompt = this.textPrompt.trim();
      if (!prompt) return;
      if (await this.handleTextCommand(prompt)) {
        this.textPrompt = '';
        return;
      }

      this.textMotionStatus = 'generating';
      this.textMotionError = '';
      this.textMotionSuccess = '';

      try {
        const requestBody = {
          text: prompt,
          motion_length: this.motionLength,
          num_inference_steps: this.inferenceSteps,
          adaptive_smooth: this.adaptiveSmooth,
          static_start: true,
          static_frames: 2,
          blend_frames: 8,
          transition_steps: this.transitionSteps
        };

        const response = await fetch(`${TEXT_MOTION_API_URL}/api/generate`, {
          method: 'POST',
          headers: this.buildSessionHeaders(true),
          body: JSON.stringify(requestBody)
        });

        const data = await response.json().catch(() => ({}));

        if (response.status === 403 && data.code === 'SESSION_FORBIDDEN') {
          this.clearSessionForbidden();
          this.textMotionError = '会话已失效，请重试生成。';
          this.textMotionStatus = 'error';
          return;
        }
        if (!response.ok || !data.success) {
          throw new Error(data.error || 'Failed to generate motion');
        }

        // Store the generated motion
        const motionData = {
          ...data.motion,
          motion_id: data.motion_id,
          text_prompt: prompt
        };

        this.generatedMotionMap.set(data.motion_id, motionData);
        this.generatedMotions = Array.from(this.generatedMotionMap.values());
        await this.trimGeneratedMotions(MAX_GENERATED_MOTIONS);

        // Update tracking helper with the new motion
        this.addMotionToTracking(motionData);

        this.textMotionSuccess = `Generated: "${prompt.substring(0, 30)}${prompt.length > 30 ? '...' : ''}"`;
        this.textPrompt = ''; // Clear input

        this.lastGeneratedMotion = motionData;
        this.playGeneratedMotion(motionData);
        this.textMotionStatus = 'connected';

      } catch (error) {
        console.error('[TextMotion] Generation failed:', error);
        this.textMotionError = error.message || 'Failed to generate motion';
        this.textMotionStatus = 'error';
      }
    },

    addMotionToTracking(motionData) {
      // 将生成的动作加入 TrackingHelper。关节顺序见项目根目录 JOINT_MAPPING.md。
      // 后端返回 joint_pos 为 policy（Isaac）顺序，Tracking 内部 ref 需 dataset 顺序，故此处做转换以与仿真一致。
      if (!this.demo?.policyRunner?.tracking) {
        console.warn('[TextMotion] Tracking helper not available');
        return;
      }

      const tracking = this.demo.policyRunner.tracking;
      const jointPosForRef = tracking.convertMotionJointPosPolicyToDataset(motionData.joint_pos);

      const motionClip = {
        joint_pos: jointPosForRef,
        root_pos: motionData.root_pos,
        root_quat: motionData.root_quat
      };

      const result = this.addMotions({
        [motionData.motion_id]: motionClip
      }, { overwrite: true });

      console.log('[TextMotion] Added motion:', result);
    },

    playGeneratedMotion(motionData) {
      if (!this.demo?.policyRunner?.tracking || !motionData?.motion_id) return;
      const accepted = this.requestMotion(motionData.motion_id);
      if (accepted) {
        this.currentMotion = motionData.motion_id;
        this.updateTrackingState();
      }
    },
    runExample(prompt) {
      this.textPrompt = prompt;
      this.generateMotionFromText();
    },
    replayLastMotion() {
      if (this.lastGeneratedMotion) {
        this.playGeneratedMotion(this.lastGeneratedMotion);
      }
    },
    listGeneratedMotions() {
      const labels = this.generatedMotions.map((m) => (m.text_prompt || m.motion_id || '').trim()).filter(Boolean);
      if (labels.length === 0) {
        this.statusMessage = '当前无已生成动作。';
      } else {
        this.statusMessage = `已生成动作(${labels.length}/${MAX_GENERATED_MOTIONS}): ${labels.join(' | ')}`;
      }
      setTimeout(() => { this.statusMessage = ''; }, 5000);
    },
    showStatus() {
      const s = this.trackingState;
      if (!s || !s.available) {
        this.statusMessage = '状态: 未就绪';
        return;
      }
      this.statusMessage = `当前动作: ${s.currentName}，${s.currentDone ? '已结束' : '播放中'}${s.isDefault ? '（默认姿态）' : ''}，已生成: ${this.generatedMotions.length}/${MAX_GENERATED_MOTIONS}`;
      setTimeout(() => { this.statusMessage = ''; }, 4000);
    },
    async clearOldMotions() {
      try {
        if (this.sessionId) {
          const res = await fetch(`${TEXT_MOTION_API_URL}/api/motions`, {
            method: 'DELETE',
            headers: this.buildSessionHeaders(false)
          });
          if (res.status === 403) {
            const d = await res.json().catch(() => ({}));
            if (d.code === 'SESSION_FORBIDDEN') this.clearSessionForbidden();
          }
        }
      } catch (error) {
        console.warn('[TextMotion] clear api failed:', error.message);
      }
      this.generatedMotionMap = new Map();
      this.generatedMotions = [];
      this.lastGeneratedMotion = null;
      this.statusMessage = '已清理当前会话下的生成动作。';
      setTimeout(() => { this.statusMessage = ''; }, 3000);
    },
    async trimGeneratedMotions(maxCount = MAX_GENERATED_MOTIONS) {
      const items = Array.from(this.generatedMotionMap.values());
      if (items.length <= maxCount) {
        return;
      }
      items.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
      const keep = items.slice(0, maxCount);
      const keepIds = new Set(keep.map((m) => m.motion_id));
      const removed = items.filter((m) => !keepIds.has(m.motion_id));
      this.generatedMotionMap = new Map(keep.map((m) => [m.motion_id, m]));
      this.generatedMotions = Array.from(this.generatedMotionMap.values());
      if (this.lastGeneratedMotion && !keepIds.has(this.lastGeneratedMotion.motion_id)) {
        this.lastGeneratedMotion = this.generatedMotions[this.generatedMotions.length - 1] ?? null;
      }
      if (removed.length > 0) {
        for (const motion of removed) {
          try {
            if (this.sessionId && motion.motion_id) {
              await fetch(`${TEXT_MOTION_API_URL}/api/motions/${motion.motion_id}`, {
                method: 'DELETE',
                headers: this.buildSessionHeaders(false)
              });
            }
          } catch (error) {
            console.warn('[TextMotion] prune api failed:', error.message);
          }
        }
      }
    },

    // ================================================================

    reapplyCustomMotions() {
      if (!this.demo || !this.customMotions) {
        return;
      }
      const names = Object.keys(this.customMotions);
      if (names.length === 0) {
        return;
      }
      this.addMotions(this.customMotions);
    },
    async onMotionUpload(files) {
      const fileList = Array.isArray(files)
        ? files
        : files instanceof FileList
          ? Array.from(files)
          : files
            ? [files]
            : [];
      if (fileList.length === 0) {
        return;
      }
      if (!this.demo) {
        this.motionUploadMessage = 'Demo not ready yet. Please wait for loading to finish.';
        this.motionUploadType = 'warning';
        this.motionUploadFiles = [];
        return;
      }

      let added = 0;
      let skipped = 0;
      let invalid = 0;
      let failed = 0;
      const prefix = '[new] ';

      for (const file of fileList) {
        try {
          const text = await file.text();
          const parsed = JSON.parse(text);
          const clip = parsed && typeof parsed === 'object' && !Array.isArray(parsed)
            ? parsed
            : null;
          if (!clip) {
            invalid += 1;
            continue;
          }

          const baseName = file.name.replace(/\.[^/.]+$/, '').trim();
          const normalizedName = baseName ? baseName : 'motion';
          const motionName = normalizedName.startsWith(prefix)
            ? normalizedName
            : `${prefix}${normalizedName}`;
          const result = this.addMotions({ [motionName]: clip });
          added += result.added.length;
          skipped += result.skipped.length;
          invalid += result.invalid.length;

          if (result.added.length > 0) {
            if (!this.customMotions) {
              this.customMotions = {};
            }
            for (const name of result.added) {
              this.customMotions[name] = clip;
            }
          }
        } catch (error) {
          console.error('Failed to read motion JSON:', error);
          failed += 1;
        }
      }

      if (added > 0) {
        this.availableMotions = this.getAvailableMotions();
      }

      const parts = [];
      if (added > 0) {
        parts.push(`Added ${added} motion${added === 1 ? '' : 's'}`);
      }
      if (skipped > 0) {
        parts.push(`Skipped ${skipped} duplicate${skipped === 1 ? '' : 's'}`);
      }
      const badCount = invalid + failed;
      if (badCount > 0) {
        parts.push(`Ignored ${badCount} invalid file${badCount === 1 ? '' : 's'}`);
      }
      if (parts.length === 0) {
        this.motionUploadMessage = 'No motions were added.';
        this.motionUploadType = 'info';
      } else {
        this.motionUploadMessage = `${parts.join('. ')}.`;
        this.motionUploadType = badCount > 0 ? 'warning' : 'success';
      }
      this.motionUploadFiles = [];
    },
    toggleCameraFollow() {
      this.cameraFollowEnabled = !this.cameraFollowEnabled;
      if (this.demo?.setFollowEnabled) {
        this.demo.setFollowEnabled(this.cameraFollowEnabled);
      }
    },
    onMotionChange(value) {
      if (!this.demo) {
        return;
      }
      if (!value || value === this.demo.params.current_motion) {
        this.currentMotion = this.demo.params.current_motion ?? value;
        return;
      }
      const accepted = this.requestMotion(value);
      if (!accepted) {
        this.currentMotion = this.demo.params.current_motion;
      } else {
        this.currentMotion = value;
        this.updateTrackingState();
      }
    },
    async onPolicyChange(value) {
      if (!this.demo || !value) {
        return;
      }
      const selected = this.policies.find((policy) => policy.value === value);
      if (!selected) {
        return;
      }
      const needsReload = selected.policyPath !== this.demo.currentPolicyPath || selected.onnxPath;
      if (!needsReload) {
        return;
      }
      const wasPaused = this.demo.params?.paused ?? false;
      this.demo.params.paused = true;
      this.isPolicyLoading = true;
      this.policyLoadError = '';
      try {
        await this.demo.reloadPolicy(selected.policyPath, {
          onnxPath: selected.onnxPath || undefined
        });
        this.policyLabel = selected.policyPath?.split('/').pop() ?? this.policyLabel;
        this.reapplyCustomMotions();
        this.availableMotions = this.getAvailableMotions();
        this.currentMotion = this.demo.params.current_motion ?? this.availableMotions[0] ?? null;
        this.updateTrackingState();
      } catch (error) {
        console.error('Failed to reload policy:', error);
        this.policyLoadError = error.toString();
      } finally {
        this.isPolicyLoading = false;
        this.demo.params.paused = wasPaused;
      }
    },
    reset() {
      if (!this.demo) {
        return;
      }
      this.demo.resetSimulation();
      this.availableMotions = this.getAvailableMotions();
      this.currentMotion = this.demo.params.current_motion ?? this.availableMotions[0] ?? null;
      this.updateTrackingState();
    },
    backToDefault() {
      if (!this.demo) {
        return;
      }
      const accepted = this.requestMotion('default');
      if (accepted) {
        this.currentMotion = 'default';
        this.updateTrackingState();
      }
    },
    runUpStand() {
      if (!this.demo) {
        return;
      }
      const list = this.getAvailableMotions();
      const name = list.includes('fallAndGetUp2_subject2')
        ? 'fallAndGetUp2_subject2'
        : list.includes('fallAndGetUp1_subject1')
          ? 'fallAndGetUp1_subject1'
          : null;
      if (!name) {
        this.statusMessage = '当前策略未加载站起动作，请检查 motions 配置。';
        setTimeout(() => { this.statusMessage = ''; }, 4000);
        return;
      }
      const accepted = this.requestMotion(name);
      if (accepted) {
        this.currentMotion = name;
        this.isUprightMonitoring = true;
        this.uprightCheckCount = 0;
        this.statusMessage = '站起动作已加载，检测到站直后自动恢复 default。';
        setTimeout(() => { this.statusMessage = ''; }, 3000);
        this.updateTrackingState();
      }
    },
    startTrackingPoll() {
      this.stopTrackingPoll();
      this.updateTrackingState();
      this.updatePerformanceStats();
      this.trackingTimer = setInterval(() => {
        this.updateTrackingState();
        this.updatePerformanceStats();
      }, 33);
    },
    stopTrackingPoll() {
      if (this.trackingTimer) {
        clearInterval(this.trackingTimer);
        this.trackingTimer = null;
      }
    },
    updateTrackingState() {
      const tracking = this.demo?.policyRunner?.tracking ?? null;
      if (!tracking) {
        this.trackingState = {
          available: false,
          currentName: 'default',
          currentDone: true,
          refIdx: 0,
          refLen: 0,
          transitionLen: 0,
          motionLen: 0,
          inTransition: false,
          isDefault: true
        };
        return;
      }
      const state = tracking.playbackState();
      this.trackingState = { ...state };
      this.availableMotions = tracking.availableMotions();
      const current = this.demo.params.current_motion ?? state.currentName ?? null;
      if (current && this.currentMotion !== current) {
        this.currentMotion = current;
      }

      const isUpMotion = state.currentName === 'fallAndGetUp2_subject2' || state.currentName === 'fallAndGetUp1_subject1';

      // 站起监测：up 后按仿真姿态判「站直」再切 default（与 sim2real UprightDetector 一致）
      if (this.isUprightMonitoring && state.available && isUpMotion && this.demo.isUpright) {
        if (this.demo.isUpright({ thresholdDeg: 15, kneeThresholdRad: 0.6 })) {
          this.uprightCheckCount += 1;
          if (this.uprightCheckCount >= this.UPRIGHT_CONSECUTIVE_FRAMES) {
            this.isUprightMonitoring = false;
            this.uprightCheckCount = 0;
            this.autoDefaultTriggered = true;
            const accepted = this.requestMotion('default');
            if (accepted) {
              this.currentMotion = 'default';
              this.statusMessage = '检测到已站直，自动切换到 default 姿态。';
              setTimeout(() => { this.statusMessage = ''; }, 3000);
            }
          }
        } else {
          this.uprightCheckCount = 0;
        }
      }

      if (this.isUprightMonitoring && (!isUpMotion || state.currentDone)) {
        this.isUprightMonitoring = false;
        this.uprightCheckCount = 0;
      }

      // 自动回 default：非 default 动作播完后，自动切回 default 姿态（仅触发一次）
      if (state.available && !state.isDefault && state.currentDone) {
        if (!this.autoDefaultTriggered) {
          this.autoDefaultTriggered = true;
          const accepted = this.requestMotion('default');
          if (accepted) {
            this.currentMotion = 'default';
            this.statusMessage = '动作已完成，自动切换到 default 姿态。';
            setTimeout(() => { this.statusMessage = ''; }, 3000);
          }
        }
      } else {
        this.autoDefaultTriggered = false;
      }
    },
    updatePerformanceStats() {
      if (!this.demo) {
        this.simStepHz = 0;
        return;
      }
      this.simStepHz = this.demo.getSimStepHz?.() ?? this.demo.simStepHz ?? 0;
    },
    onRenderScaleChange(value) {
      if (!this.demo) {
        return;
      }
      this.demo.setRenderScale(value);
    },
    getAvailableMotions() {
      const tracking = this.demo?.policyRunner?.tracking ?? null;
      return tracking ? tracking.availableMotions() : [];
    },
    addMotions(motions, options = {}) {
      const tracking = this.demo?.policyRunner?.tracking ?? null;
      if (!tracking) {
        return { added: [], skipped: [], invalid: [] };
      }
      return tracking.addMotions(motions, options);
    },
    requestMotion(name) {
      const tracking = this.demo?.policyRunner?.tracking ?? null;
      if (!tracking || !this.demo) {
        return false;
      }
      const state = this.demo.readPolicyState();
      const accepted = tracking.requestMotion(name, state);
      if (accepted) {
        this.demo.params.current_motion = name;
      }
      return accepted;
    }
  },
  mounted() {
    this.customMotions = {};
    this.isSafari = this.detectSafari();
    this.updateScreenState();
    this.resize_listener = () => {
      this.updateScreenState();
    };
    window.addEventListener('resize', this.resize_listener);
    this.init();
    this.keydown_listener = (event) => {
      if (event.code === 'Backspace') {
        this.reset();
      }
    };
    document.addEventListener('keydown', this.keydown_listener);
  },
  beforeUnmount() {
    this.stopTrackingPoll();
    document.removeEventListener('keydown', this.keydown_listener);
    if (this.resize_listener) {
      window.removeEventListener('resize', this.resize_listener);
    }
  }
};
</script>

<style scoped>
.controls {
  position: fixed;
  top: 20px;
  right: 20px;
  width: 340px;
  z-index: 1000;
}

/* 手机/小屏：底部抽屉式控制面板，便于输入文本指令 */
@media (max-width: 499px), (max-height: 699px) {
  .controls {
    top: auto;
    right: 0;
    bottom: 0;
    left: 0;
    width: 100%;
    max-height: 72vh;
    padding-bottom: env(safe-area-inset-bottom, 0);
    display: flex;
    flex-direction: column;
  }
  .controls-card {
    max-height: 72vh;
    border-radius: 16px 16px 0 0;
    box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.15);
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
  }
  .controls-body {
    max-height: none;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
  }
  /* 触控友好：输入框 16px 避免 iOS 聚焦放大 */
  .controls--mobile .text-to-motion-section :deep(textarea),
  .controls--mobile .text-to-motion-section :deep(.v-field__input) {
    font-size: 16px !important;
    min-height: 44px;
  }
  .controls--mobile .command-buttons .v-btn {
    min-height: 44px;
    padding: 0 14px;
  }
  .controls--mobile .v-btn.flex-grow-1 {
    min-height: 44px;
  }
  .controls--mobile .example-chip {
    min-height: 40px;
  }
}

.global-alerts {
  position: fixed;
  top: 20px;
  left: 16px;
  right: 16px;
  max-width: 520px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 1200;
}

.small-screen-alert {
  width: 100%;
}

.safari-alert {
  width: 100%;
}

.controls-card {
  max-height: calc(100vh - 40px);
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
}

.controls-title {
  font-size: 1rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  padding: 14px 16px 8px;
}

.controls-body {
  max-height: calc(100vh - 160px);
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 8px 16px 16px;
}

.section-divider {
  height: 1px;
  background: rgba(0, 0, 0, 0.08);
  margin: 12px 0;
}

.section-label {
  display: block;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: rgba(0, 0, 0, 0.55);
  margin-bottom: 8px;
}

.usage-instructions {
  background: linear-gradient(135deg, rgba(25, 118, 210, 0.06) 0%, rgba(25, 118, 210, 0.02) 100%);
  border-radius: 10px;
  padding: 12px 14px;
  border: 1px solid rgba(25, 118, 210, 0.12);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.usage-heading {
  font-size: 0.9rem;
  font-weight: 700;
  margin: 0 0 2px;
  color: rgba(0, 0, 0, 0.85);
  letter-spacing: 0.01em;
}

.usage-desc {
  font-size: 0.8rem;
  line-height: 1.4;
  color: rgba(0, 0, 0, 0.7);
  margin: 0;
}

.usage-bullets {
  margin: 4px 0 6px 14px;
  padding: 0;
  font-size: 0.78rem;
  line-height: 1.45;
  color: rgba(0, 0, 0, 0.65);
}

.usage-bullets li {
  margin-bottom: 2px;
}

.usage-cmds {
  font-size: 0.78rem;
  line-height: 1.5;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.usage-cmds-label {
  font-weight: 700;
  font-size: 0.75rem;
  color: rgba(0, 0, 0, 0.75);
  margin-bottom: 2px;
}

.usage-cmd-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}

.usage-cmd-row kbd {
  font-family: ui-monospace, monospace;
  font-size: 0.72rem;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.08);
  border: 1px solid rgba(0, 0, 0, 0.1);
  flex-shrink: 0;
}

.command-section {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.command-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.example-prompts .text-caption {
  font-weight: 600;
  color: rgba(0, 0, 0, 0.6);
  margin-bottom: 6px;
}

.example-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 6px;
}

.example-chip {
  text-transform: none;
  white-space: normal;
  max-width: 100%;
  font-size: 0.78rem;
}

.motion-status {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.motion-groups {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
  max-height: 200px;
  overflow-y: auto;
}

.motion-group {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.motion-chip {
  text-transform: none;
  font-size: 0.7rem;
}

.status-legend {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.status-name {
  font-weight: 600;
}

.policy-file {
  display: block;
  margin-top: 4px;
}


.upload-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.upload-toggle {
  padding: 0;
  min-height: unset;
  font-size: 0.85rem;
  text-transform: none;
}

.motion-progress-no-animation,
.motion-progress-no-animation *,
.motion-progress-no-animation::before,
.motion-progress-no-animation::after {
  transition: none !important;
  animation: none !important;
}

.motion-progress-no-animation :deep(.v-progress-linear__determinate),
.motion-progress-no-animation :deep(.v-progress-linear__indeterminate),
.motion-progress-no-animation :deep(.v-progress-linear__background) {
  transition: none !important;
  animation: none !important;
}

/* Text-to-Motion Section Styles */
.text-to-motion-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.advanced-options {
  background: rgba(0, 0, 0, 0.03);
  border-radius: 8px;
  padding: 8px;
}

.generated-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.generated-legend {
  margin-bottom: 2px;
}

.generated-hint {
  font-size: 0.72rem;
  color: rgba(0, 0, 0, 0.55);
  margin: 0 0 6px;
}

.generated-motions-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
  max-height: 120px;
  overflow-y: auto;
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
