// Popup script for Whispa extension
const API_BASE_URL = 'http://localhost:5000';
document.addEventListener('DOMContentLoaded', function () {
  // DOM elements
  const captureBtn = document.getElementById('captureBtn');
  const recordBtn = document.getElementById('recordBtn');
  const generateBtn = document.getElementById('generateBtn');
  const copyBtn = document.getElementById('copyBtn');
  const exportBtn = document.getElementById('exportBtn');
  const linearBtn = document.getElementById('linearBtn');

  const captureStatus = document
    .getElementById('captureStatus')
    .querySelector('.value');
  const audioStatus = document
    .getElementById('audioStatus')
    .querySelector('.value');
  const ocrStatus = document
    .getElementById('ocrStatus')
    .querySelector('.value');
  const imagePreview = document.getElementById('imagePreview');
  const capturedImage = document.getElementById('capturedImage');
  const notesPreview = document.getElementById('notesPreview');
  const notesContent = document.getElementById('notes');

  // Settings Modal Elements
  const settingsBtn = document.getElementById('settingsBtn');
  const settingsModal = document.getElementById('settingsModal');
  const cancelSettingsBtn = document.getElementById('cancelSettingsBtn');
  const saveSettingsBtn = document.getElementById('saveSettingsBtn');
  const linearApiKey = document.getElementById('linearApiKey');
  const linearTeamId = document.getElementById('linearTeamId');
  const linearLabel = document.getElementById('linearLabel');
  const geminiApiKey = document.getElementById('geminiApiKey');

  // State variables
  let isRecording = false;
  let mediaRecorder = null;
  let audioChunks = [];
  let captureData = null;
  let audioData = null;
  let whispaEnabled = true;
  let settings = {};

  // Initialize extension state
  chrome.storage.local.get(['whispaEnabled', 'settings'], function (result) {
    // Default to enabled if not set
    whispaEnabled = result.whispaEnabled !== false;
    if (result.settings) {
      settings = result.settings;
      linearApiKey.value = settings.linearApiKey || '';
      linearTeamId.value = settings.linearTeamId || '';
      linearLabel.value = settings.linearLabel || '';
      geminiApiKey.value = settings.geminiApiKey || '';
    }
    updateUIState();
  });

  // Screen capture functionality
  captureBtn.addEventListener('click', async () => {
    try {
      // Disable button during capture
      captureBtn.disabled = true;
      captureStatus.textContent = 'Capturing...';

      // Send message to background script to capture the current tab
      chrome.runtime.sendMessage({ action: 'captureScreen' }, (response) => {
        if (response && response.success) {
          captureData = response.imageData;
          captureStatus.textContent = 'Captured';

          // Show image preview
          capturedImage.src = captureData;
          imagePreview.classList.remove('hidden');

          // Enable generate button if both capture and audio are ready
          if (audioData) {
            generateBtn.disabled = false;
          }
        } else {
          captureStatus.textContent = 'Failed to capture';
          console.error(
            'Screen capture failed:',
            response?.error || 'Unknown error'
          );
        }

        // Re-enable button
        captureBtn.disabled = false;
      });
    } catch (error) {
      console.error('Error during screen capture:', error);
      captureStatus.textContent = 'Error: ' + error.message;
      captureBtn.disabled = false;
    }
  });

  // Audio recording functionality
  recordBtn.addEventListener('click', async () => {
    if (isRecording) {
      stopRecording();
    } else {
      try {
        // Disable button during permission request
        recordBtn.disabled = true;

        const stream = await navigator.mediaDevices.getUserMedia({
          audio: true,
        });
        startRecording(stream);

        // Re-enable button after permission granted
        recordBtn.disabled = false;
      } catch (error) {
        console.error('Error accessing microphone:', error);
        audioStatus.textContent = 'Microphone access denied';
        recordBtn.disabled = false;
      }
    }
  });

  function startRecording(stream) {
    audioStatus.textContent = 'Recording...';
    recordBtn.querySelector('.record-text').textContent = 'Stop';

    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];

    mediaRecorder.addEventListener('dataavailable', (event) => {
      audioChunks.push(event.data);
    });

    mediaRecorder.addEventListener('stop', () => {
      const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });

      // Convert Blob to base64 data URI
      const reader = new FileReader();
      reader.onloadend = function () {
        audioData = reader.result; // This will be a proper data URI with format "data:audio/webm;base64,..."
        audioStatus.textContent = 'Recorded';
        recordBtn.querySelector('.record-text').textContent = 'Record';
        isRecording = false;

        // Enable generate button if both capture and audio are ready
        if (captureData) {
          generateBtn.disabled = false;
        }
      };
      reader.readAsDataURL(audioBlob);
    });

    mediaRecorder.start();
    isRecording = true;
  }

  function stopRecording() {
    if (mediaRecorder && isRecording) {
      mediaRecorder.stop();
      mediaRecorder.stream.getTracks().forEach((track) => track.stop());
    }
  }

  // Listen for OCR progress updates from background script
  chrome.runtime.onMessage.addListener((message) => {
    console.log('Received message from background:', message);

    if (message.action === 'ocrProgress') {
      const progressBar = document.getElementById('progressBar');
      const progressStatus = document.getElementById('progressStatus');
      const percent =
        message.progress && typeof message.progress.percent === 'number'
          ? message.progress.percent
          : message.progress && typeof message.progress.progress === 'number'
          ? Math.round(message.progress.progress * 100)
          : 0;

      // Update progress bar
      progressBar.style.width = `${percent}%`;

      // Reset classes
      progressBar.classList.remove('error');
      progressStatus.classList.remove('success', 'error');

      ocrStatus.textContent = `Processing: ${percent}%`;
      progressStatus.textContent = `${percent}%`;

      // Update status based on progress state
      if (message.progress && message.progress.status === 'error') {
        progressBar.classList.add('error');
        progressStatus.classList.add('error');
        progressStatus.textContent = 'Failed';
        ocrStatus.textContent = 'Failed';
      } else if (
        percent === 100 ||
        (message.progress && message.progress.status === 'completed')
      ) {
        progressStatus.classList.add('success');
        progressStatus.textContent = 'Success';
        ocrStatus.textContent = 'Completed';
      }
    }

    // Listen for note generation progress updates
    if (message.action === 'noteGenerationProgress') {
      const progressBar = document.getElementById('progressBar');
      const progressStatus = document.getElementById('progressStatus');

      // Update the status display
      ocrStatus.textContent = message.message;

      // Reset classes
      progressBar.classList.remove('error');
      progressStatus.classList.remove('success', 'error');

      if (message.status === 'starting') {
        progressBar.style.width = '10%';
        progressStatus.textContent = 'Starting...';
      } else if (message.status === 'processing') {
        progressBar.style.width = '50%';
        progressStatus.textContent = 'Processing...';
      } else if (message.status === 'generating') {
        progressBar.style.width = '75%';
        progressStatus.textContent = 'Generating...';
      } else if (message.status === 'complete') {
        progressBar.style.width = '100%';
        progressStatus.classList.add('success');
        progressStatus.textContent = 'Success';

        // Notes should be available in storage now
        chrome.storage.local.get(['lastNotes'], function (result) {
          if (result.lastNotes && result.lastNotes.content) {
            notesContent.textContent = result.lastNotes.content;
            notesPreview.classList.remove('hidden');

            // Enable copy, export, and Linear buttons
            copyBtn.disabled = false;
            exportBtn.disabled = false;
            linearBtn.disabled = false;
          }
        });

        generateBtn.disabled = false;
        generateBtn.querySelector('.generate-text').textContent = 'Generate';
        const spinner = generateBtn.querySelector('.spinner');
        if (spinner) spinner.classList.add('hidden');
      } else if (message.status === 'error') {
        progressBar.style.width = '100%';
        progressBar.classList.add('error');
        progressStatus.classList.add('error');
        progressStatus.textContent = 'Failed';

        generateBtn.disabled = false;
        generateBtn.querySelector('.generate-text').textContent = 'Generate';
        const spinner = generateBtn.querySelector('.spinner');
        if (spinner) spinner.classList.add('hidden');
        alert('Note generation failed: ' + message.message);
      }
    }
  });

  // Generate notes functionality
  generateBtn.addEventListener('click', async () => {
    if (!captureData || !audioData) {
      console.error('Missing capture data or audio data');
      return;
    }

    try {
      generateBtn.disabled = true;
      const generateText = generateBtn.querySelector('.generate-text');
      const originalText = generateText.textContent;
      generateText.textContent = 'Processing...';

      // Add spinner if it exists
      const spinner = generateBtn.querySelector('.spinner');
      if (spinner) spinner.classList.remove('hidden');

      ocrStatus.textContent = 'Processing...';

      // Send data to background script for processing
      chrome.runtime.sendMessage(
        {
          action: 'generateNotes',
          captureData: captureData,
          audioData: audioData,
        },
        (response) => {
          if (response && response.success) {
            ocrStatus.textContent = 'Completed';

            // Display the generated notes
            notesContent.textContent = response.notes;
            notesPreview.classList.remove('hidden');

            // Enable copy and export buttons
            copyBtn.disabled = false;
            exportBtn.disabled = false;
          } else {
            ocrStatus.textContent = 'Failed';
            console.error(
              'Processing failed:',
              response?.error || 'Unknown error'
            );
          }

          // Reset button state
          generateBtn.disabled = false;
          generateText.textContent = originalText;
          if (spinner) spinner.classList.add('hidden');
        }
      );
    } catch (error) {
      console.error('Error during processing:', error);
      ocrStatus.textContent = 'Error: ' + error.message;
      generateBtn.disabled = false;
    }
  });

  // Copy notes functionality
  copyBtn.addEventListener('click', () => {
    const notesText = notesContent.textContent;
    if (notesText && notesText !== 'Your generated notes will appear here...') {
      navigator.clipboard
        .writeText(notesText)
        .then(() => {
          // Visual feedback for copy success
          const originalColor = copyBtn.style.color;
          copyBtn.style.color = '#4caf50';
          setTimeout(() => {
            copyBtn.style.color = originalColor;
          }, 1000);
        })
        .catch((err) => {
          console.error('Failed to copy notes:', err);
        });
    }
  });

  // Export notes functionality
  exportBtn.addEventListener('click', () => {
    const notesText = notesContent.textContent;
    if (notesText && notesText !== 'Your generated notes will appear here...') {
      const blob = new Blob([notesText], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'whispa-notes.md';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  });

  // Linear integration functionality
  const linearModal = document.getElementById('linearModal');
  const ticketTitle = document.getElementById('ticketTitle');
  const ticketDescription = document.getElementById('ticketDescription');
  const ticketPriority = document.getElementById('ticketPriority');
  const cancelLinearBtn = document.getElementById('cancelLinearBtn');
  const submitLinearBtn = document.getElementById('submitLinearBtn');
  const linearSuccess = document.getElementById('linearSuccess');

  // Open Linear modal when Linear button is clicked
  linearBtn.addEventListener('click', () => {
    // Pre-fill the form with the generated notes
    const notesText = notesContent.textContent;
    if (notesText && notesText !== 'Your generated notes will appear here...') {
      // Extract a title from the first line or first 50 characters
      const firstLine = notesText.split('\n')[0];
      ticketTitle.value =
        firstLine.length > 50 ? firstLine.substring(0, 50) + '...' : firstLine;

      // Use the full notes as description
      ticketDescription.value = notesText;

      // Show the modal
      linearModal.classList.remove('hidden');
    }
  });

  // Close Linear modal when Cancel button is clicked
  cancelLinearBtn.addEventListener('click', () => {
    linearModal.classList.add('hidden');
    linearSuccess.classList.add('hidden');
  });

  // Submit Linear ticket when Submit button is clicked
  submitLinearBtn.addEventListener('click', async () => {
    if (!ticketTitle.value.trim()) {
      alert('Please enter a ticket title');
      return;
    }

    try {
      submitLinearBtn.disabled = true;
      submitLinearBtn.textContent = 'Creating...';

      // Get the last generated notes ID from storage
      chrome.storage.local.get(['lastNotes'], async function (result) {
        if (!result.lastNotes) {
          submitLinearBtn.disabled = false;
          submitLinearBtn.textContent = 'Create Ticket';
          showError('No notes found. Please generate notes first.');
          return;
        }

        // Use timestamp as ID if id is not available and ensure it's a string
        const summaryId = String(
          result.lastNotes.id || result.lastNotes.timestamp || Date.now()
        );

        // Send request to create Linear ticket
        try {
          const response = await fetch(
            `${API_BASE_URL}/routers/integrations/ticket`,
            {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({
                summary_id: summaryId,
                integration_type: 'linear',
                title: ticketTitle.value,
                description: ticketDescription.value,
                priority: ticketPriority.value,
                labels: ['30d98260-9069-4a76-bee7-e3c377e4a256'],
              }),
            }
          );

          if (!response.ok) {
            const errorData = await response.json();
            const errorMessage =
              errorData.detail ||
              `Failed to create ticket: ${response.status} ${response.statusText}`;

            // Special handling for "No active Linear integration" error
            if (errorMessage.includes('No active Linear integration found')) {
              throw new Error(
                'No Linear integration configured. Please contact your administrator to set up Linear integration.'
              );
            }

            throw new Error(errorMessage);
          }

          const data = await response.json();

          // Show success message
          linearSuccess.classList.remove('hidden');

          // Reset form after 2 seconds and close modal
          setTimeout(() => {
            linearModal.classList.add('hidden');
            linearSuccess.classList.add('hidden');
            ticketTitle.value = '';
            ticketDescription.value = '';
            ticketPriority.value = 'medium';
            submitLinearBtn.disabled = false;
            submitLinearBtn.textContent = 'Create Ticket';
          }, 2000);
        } catch (error) {
          console.error('Error creating ticket:', error);
          showError(
            error.message || 'Failed to create ticket. Please try again.'
          );
          submitLinearBtn.disabled = false;
          submitLinearBtn.textContent = 'Create Ticket';
        }
      });
    } catch (error) {
      console.error('Error creating Linear ticket:', error);
      alert(`Failed to create Linear ticket: ${error.message}`);
      submitLinearBtn.disabled = false;
      submitLinearBtn.textContent = 'Create Ticket';
    }
  });

  // Helper function to show toast notifications
  function showToast(message, duration = 3000) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
      toast.remove();
    }, duration);
  }

  // Settings Modal Functionality
  settingsBtn.addEventListener('click', () => {
    settingsModal.classList.remove('hidden');
  });

  cancelSettingsBtn.addEventListener('click', () => {
    settingsModal.classList.add('hidden');
  });

  saveSettingsBtn.addEventListener('click', () => {
    settings = {
      linearApiKey: linearApiKey.value,
      linearTeamId: linearTeamId.value,
      linearLabel: linearLabel.value,
      geminiApiKey: geminiApiKey.value,
    };
    chrome.storage.local.set({ settings }, () => {
      showToast('Settings saved successfully!');
      settingsModal.classList.add('hidden');
      updateUIState();
    });
  });

  // Helper function to update UI based on extension state
  function updateUIState() {
    captureBtn.disabled = !whispaEnabled;
    recordBtn.disabled = !whispaEnabled;
    generateBtn.disabled = !whispaEnabled || !captureData || !audioData;

    // Disable export and linear buttons if Linear API key is not set
    if (settings.linearApiKey && settings.linearTeamId) {
      exportBtn.disabled = false;
      linearBtn.disabled = false;
    } else {
      exportBtn.disabled = true;
      linearBtn.disabled = true;
    }
  }

  // Check for saved collapsed state
  chrome.storage.local.get(['whispaCollapsed'], function (result) {
    if (result.whispaCollapsed) {
      document.body.classList.add('collapsed');
    }
  });
});
