// Popup script for Whispa extension

document.addEventListener('DOMContentLoaded', function () {
  // DOM elements
  const captureBtn = document.getElementById('captureBtn');
  const recordBtn = document.getElementById('recordBtn');
  const generateBtn = document.getElementById('generateBtn');
  const copyBtn = document.getElementById('copyBtn');
  const exportBtn = document.getElementById('exportBtn');

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

  // State variables
  let isRecording = false;
  let mediaRecorder = null;
  let audioChunks = [];
  let captureData = null;
  let audioData = null;
  let whispaEnabled = true;

  // Initialize extension state
  chrome.storage.local.get(['whispaEnabled'], function (result) {
    // Default to enabled if not set
    whispaEnabled = result.whispaEnabled !== false;
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

            // Enable copy and export buttons
            copyBtn.disabled = false;
            exportBtn.disabled = false;
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

  // Helper function to update UI based on extension state
  function updateUIState() {
    captureBtn.disabled = !whispaEnabled;
    recordBtn.disabled = !whispaEnabled;
    generateBtn.disabled = !whispaEnabled || !captureData || !audioData;
  }

  // Check for saved collapsed state
  chrome.storage.local.get(['whispaCollapsed'], function (result) {
    if (result.whispaCollapsed) {
      document.body.classList.add('collapsed');
    }
  });
});
