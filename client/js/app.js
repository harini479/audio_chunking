/* =============================================
   Recording Chunker — Frontend App
   ============================================= */

const API_BASE = '/api/recordings';

// DOM Elements
const dropzone = document.getElementById('upload-dropzone');
const fileInput = document.getElementById('file-input');
const uploadProgress = document.getElementById('upload-progress');
const progressFilename = document.getElementById('progress-filename');
const progressPercent = document.getElementById('progress-percent');
const progressBarFill = document.getElementById('progress-bar-fill');
const progressStatus = document.getElementById('progress-status');
const recordingsGrid = document.getElementById('recordings-grid');
const loadingSpinner = document.getElementById('loading-spinner');
const emptyState = document.getElementById('empty-state');
const btnRefresh = document.getElementById('btn-refresh');
const toastContainer = document.getElementById('toast-container');

// Polling interval ID for processing recordings
let pollingInterval = null;

/* =============================================
   Initialization
   ============================================= */
document.addEventListener('DOMContentLoaded', () => {
  setupDropzone();
  setupRefresh();
  loadRecordings();
});

/* =============================================
   Drag & Drop + File Selection
   ============================================= */
function setupDropzone() {
  // Click to browse
  dropzone.addEventListener('click', () => fileInput.click());

  // File selected
  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      uploadFile(e.target.files[0]);
    }
  });

  // Drag events
  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('drag-over');
  });

  dropzone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    dropzone.classList.remove('drag-over');
  });

  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('drag-over');

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      // Validate file type
      const file = files[0];
      if (file.type.startsWith('audio/') || file.type.startsWith('video/')) {
        uploadFile(file);
      } else {
        showToast('Only audio and video files are supported', 'error');
      }
    }
  });
}

/* =============================================
   File Upload with Progress
   ============================================= */
function uploadFile(file) {
  // Show progress UI
  uploadProgress.style.display = 'block';
  progressFilename.textContent = file.name;
  progressPercent.textContent = '0%';
  progressBarFill.style.width = '0%';
  progressStatus.textContent = 'Uploading...';

  const formData = new FormData();
  formData.append('recording', file);

  const xhr = new XMLHttpRequest();

  // Track progress
  xhr.upload.addEventListener('progress', (e) => {
    if (e.lengthComputable) {
      const percent = Math.round((e.loaded / e.total) * 100);
      progressPercent.textContent = `${percent}%`;
      progressBarFill.style.width = `${percent}%`;

      if (percent >= 100) {
        progressStatus.textContent = 'Processing upload...';
      }
    }
  });

  // Upload complete
  xhr.addEventListener('load', () => {
    if (xhr.status >= 200 && xhr.status < 300) {
      const response = JSON.parse(xhr.responseText);
      progressStatus.textContent = '✓ Upload complete — chunking in progress...';
      progressBarFill.style.width = '100%';

      showToast(`"${file.name}" uploaded! Chunking started...`, 'success');

      // Reset after a short delay
      setTimeout(() => {
        uploadProgress.style.display = 'none';
        fileInput.value = '';
      }, 2000);

      // Reload recordings and start polling
      loadRecordings();
      startPolling();
    } else {
      let errorMsg = 'Upload failed';
      try {
        const response = JSON.parse(xhr.responseText);
        errorMsg = response.error || errorMsg;
      } catch (e) {}
      progressStatus.textContent = `✗ ${errorMsg}`;
      showToast(errorMsg, 'error');
    }
  });

  // Upload error
  xhr.addEventListener('error', () => {
    progressStatus.textContent = '✗ Upload failed — network error';
    showToast('Upload failed. Please check your connection.', 'error');
  });

  xhr.open('POST', `${API_BASE}/upload`);
  xhr.send(formData);
}

/* =============================================
   Load and Render Recordings
   ============================================= */
async function loadRecordings() {
  try {
    loadingSpinner.style.display = 'flex';
    emptyState.style.display = 'none';

    const response = await fetch(API_BASE);
    const recordings = await response.json();

    loadingSpinner.style.display = 'none';

    if (recordings.length === 0) {
      emptyState.style.display = 'flex';
      recordingsGrid.innerHTML = '';
      stopPolling();
      return;
    }

    emptyState.style.display = 'none';
    renderRecordings(recordings);

    // Check if any are still processing
    const hasProcessing = recordings.some((r) => r.status === 'processing');
    if (hasProcessing) {
      startPolling();
    } else {
      stopPolling();
    }
  } catch (error) {
    loadingSpinner.style.display = 'none';
    console.error('Failed to load recordings:', error);
    showToast('Failed to load recordings', 'error');
  }
}

function renderRecordings(recordings) {
  // Keep track of expanded state
  const expandedIds = new Set();
  document.querySelectorAll('.chunks-panel.expanded').forEach((panel) => {
    expandedIds.add(panel.dataset.id);
  });

  recordingsGrid.innerHTML = recordings
    .map((rec, idx) => createRecordingCard(rec, expandedIds.has(rec._id)))
    .join('');

  // Re-attach event listeners
  document.querySelectorAll('.recording-header').forEach((header) => {
    header.addEventListener('click', () => toggleChunks(header.dataset.id));
  });

  document.querySelectorAll('.btn-delete').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      deleteRecording(btn.dataset.id, btn.dataset.name);
    });
  });

  // Load chunks for expanded panels
  expandedIds.forEach((id) => loadChunks(id));
}

function createRecordingCard(recording, isExpanded) {
  const isAudio = recording.mimetype.startsWith('audio/');
  const iconSvg = isAudio
    ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>'
    : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>';

  return `
    <div class="recording-card" id="recording-${recording._id}">
      <div class="recording-header" data-id="${recording._id}">
        <div class="recording-info">
          <div class="recording-icon">${iconSvg}</div>
          <div class="recording-details">
            <div class="recording-name" title="${escapeHtml(recording.originalName)}">${escapeHtml(recording.originalName)}</div>
            <div class="recording-meta">
              <span>${formatFileSize(recording.size)}</span>
              <span>•</span>
              <span>${recording.duration ? formatDuration(recording.duration) : '—'}</span>
              <span>•</span>
              <span>${recording.chunkCount || 0} chunks</span>
              <span>•</span>
              <span>${formatDate(recording.createdAt)}</span>
            </div>
          </div>
        </div>
        <div class="recording-actions">
          <span class="status-badge ${recording.status}">${recording.status}</span>
          <button class="btn-delete" data-id="${recording._id}" data-name="${escapeHtml(recording.originalName)}" title="Delete">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
            </svg>
          </button>
          <span class="toggle-chevron ${isExpanded ? 'expanded' : ''}">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </span>
        </div>
      </div>
      <div class="chunks-panel ${isExpanded ? 'expanded' : ''}" data-id="${recording._id}">
        <div class="chunks-content">
          <div class="chunks-grid" id="chunks-${recording._id}">
            <div class="loading-spinner" style="grid-column: 1 / -1;">
              <div class="spinner"></div>
              <p>Loading chunks...</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
}

/* =============================================
   Toggle & Load Chunks
   ============================================= */
function toggleChunks(recordingId) {
  const panel = document.querySelector(`.chunks-panel[data-id="${recordingId}"]`);
  const chevron = document.querySelector(`#recording-${recordingId} .toggle-chevron`);

  if (!panel || !chevron) return;

  const isExpanded = panel.classList.contains('expanded');

  if (isExpanded) {
    panel.classList.remove('expanded');
    chevron.classList.remove('expanded');
  } else {
    panel.classList.add('expanded');
    chevron.classList.add('expanded');
    loadChunks(recordingId);
  }
}

async function loadChunks(recordingId) {
  const chunksGrid = document.getElementById(`chunks-${recordingId}`);
  if (!chunksGrid) return;

  try {
    const response = await fetch(`${API_BASE}/${recordingId}/chunks`);
    const chunks = await response.json();

    if (chunks.length === 0) {
      chunksGrid.innerHTML = '<p style="color: var(--text-muted); padding: 16px; grid-column: 1 / -1;">No chunks yet. Processing may still be in progress...</p>';
      return;
    }

    // Determine if audio or video based on file extension
    chunksGrid.innerHTML = chunks.map((chunk) => createChunkCard(chunk)).join('');
  } catch (error) {
    console.error('Failed to load chunks:', error);
    chunksGrid.innerHTML = '<p style="color: var(--accent-red); padding: 16px; grid-column: 1 / -1;">Failed to load chunks</p>';
  }
}

function createChunkCard(chunk) {
  const ext = chunk.filename.split('.').pop().toLowerCase();
  const audioExts = ['mp3', 'wav', 'm4a', 'aac', 'ogg', 'flac'];
  const isAudio = audioExts.includes(ext);

  const streamUrl = `${API_BASE}/chunks/file/${chunk.filename}`;

  const player = isAudio
    ? `<div class="chunk-player"><audio controls preload="metadata"><source src="${streamUrl}"></audio></div>`
    : `<div class="chunk-player"><video controls preload="metadata"><source src="${streamUrl}"></video></div>`;

  return `
    <div class="chunk-card">
      <div class="chunk-header">
        <span class="chunk-index">Chunk ${chunk.chunkIndex + 1}</span>
        <span class="chunk-size">${formatFileSize(chunk.size)}</span>
      </div>
      <div class="chunk-times">
        <span class="chunk-time-badge">${formatDuration(chunk.startTime)}</span>
        <span class="chunk-arrow">→</span>
        <span class="chunk-time-badge">${formatDuration(chunk.endTime)}</span>
      </div>
      ${player}
      <a href="${streamUrl}" download="${chunk.filename}" class="chunk-download">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
        </svg>
        Download
      </a>
    </div>
  `;
}

/* =============================================
   Delete Recording
   ============================================= */
async function deleteRecording(id, name) {
  if (!confirm(`Delete "${name}" and all its chunks?`)) return;

  try {
    const response = await fetch(`${API_BASE}/${id}`, { method: 'DELETE' });
    if (response.ok) {
      showToast(`"${name}" deleted`, 'info');
      loadRecordings();
    } else {
      const data = await response.json();
      showToast(data.error || 'Delete failed', 'error');
    }
  } catch (error) {
    showToast('Delete failed', 'error');
  }
}

/* =============================================
   Polling for Processing Status
   ============================================= */
function startPolling() {
  if (pollingInterval) return;
  pollingInterval = setInterval(loadRecordings, 5000);
}

function stopPolling() {
  if (pollingInterval) {
    clearInterval(pollingInterval);
    pollingInterval = null;
  }
}

/* =============================================
   Refresh Button
   ============================================= */
function setupRefresh() {
  btnRefresh.addEventListener('click', () => {
    btnRefresh.classList.add('spinning');
    loadRecordings().then(() => {
      setTimeout(() => btnRefresh.classList.remove('spinning'), 600);
    });
  });
}

/* =============================================
   Toast Notifications
   ============================================= */
function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  toastContainer.appendChild(toast);

  // Auto-dismiss after 4s
  setTimeout(() => {
    toast.classList.add('toast-out');
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

/* =============================================
   Utility Functions
   ============================================= */
function formatFileSize(bytes) {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let unitIndex = 0;
  let size = bytes;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }
  return `${size.toFixed(size < 10 ? 2 : 1)} ${units[unitIndex]}`;
}

function formatDuration(seconds) {
  if (!seconds && seconds !== 0) return '—';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);

  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }
  return `${m}:${String(s).padStart(2, '0')}`;
}

function formatDate(dateStr) {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now - date;
  const diffMin = Math.floor(diffMs / 60000);

  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffMin < 1440) return `${Math.floor(diffMin / 60)}h ago`;

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
