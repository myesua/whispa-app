// Background script for Whispa extension
const API_BASE_URL = 'http://localhost:5000';
// Listen for messages from popup or content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'captureScreen') {
    captureCurrentTab()
      .then((imageData) => {
        sendResponse({ success: true, imageData });
      })
      .catch((error) => {
        console.error('Error capturing screen:', error);
        sendResponse({ success: false, error: error.message });
      });
    return true; // Indicates async response
  }

  if (request.action === 'generateNotes') {
    generateNotes(request.captureData, request.audioData)
      .then((notes) => {
        sendResponse({ success: true, notes });
      })
      .catch((error) => {
        console.error('Error generating notes:', error);
        sendResponse({ success: false, error: error.message });
      });
    return true; // Indicates async response
  }

  if (request.action === 'processOCR') {
    processOCR(request.imageData, request.options)
      .then((result) => {
        sendResponse({ success: true, result });
      })
      .catch((error) => {
        console.error('Error processing OCR:', error);
        sendResponse({ success: false, error: error.message });
      });
    return true; // Indicates async response
  }
});

// Function to capture the current tab
async function captureCurrentTab() {
  try {
    // Get the active tab
    const [tab] = await chrome.tabs.query({
      active: true,
      currentWindow: true,
    });

    if (!tab) {
      throw new Error('No active tab found');
    }

    // Capture the visible area of the tab
    const imageData = await chrome.tabs.captureVisibleTab(null, {
      format: 'png',
    });

    // Save the capture to storage for later use
    await chrome.storage.local.set({
      lastCapture: {
        imageData,
        timestamp: Date.now(),
        url: tab.url,
        title: tab.title,
      },
    });

    return imageData;
  } catch (error) {
    console.error('Error in captureCurrentTab:', error);
    throw error;
  }
}

// Function to process captured screen and audio to generate notes
async function generateNotes(captureData, audioData) {
  try {
    // Send progress update to popup
    chrome.runtime.sendMessage({
      action: 'noteGenerationProgress',
      status: 'starting',
      message: 'Starting OCR processing...',
    });

    // Process the captured screen with real OCR
    const ocrResult = await processOCR(captureData);
    const ocrText = ocrResult.text || '';
    const imageData = ocrResult.image_data || ''; // Get the image data from OCR response

    console.log('OCR processing complete, text length:', ocrText.length);

    // Send progress update to popup
    chrome.runtime.sendMessage({
      action: 'noteGenerationProgress',
      status: 'processing',
      message: 'Processing audio transcription...',
    });

    // Process speech-to-text
    const transcription = await processSTT(audioData);
    console.log('Audio transcription complete, text length:', transcription ? transcription.length : 0);

    // Send progress update to popup
    chrome.runtime.sendMessage({
      action: 'noteGenerationProgress',
      status: 'generating',
      message: 'Generating AI notes...',
    });

    // Send to our API for note generation with Gemini
    console.log('Sending data to note generation API:', {
      ocrTextLength: ocrText ? ocrText.length : 0,
      transcriptionLength: transcription ? transcription.length : 0,
      hasImageData: !!imageData
    });

    const response = await fetch(`${API_BASE_URL}/api/notes/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        ocrText: ocrText || '',
        transcription: transcription || '',
        imageData: imageData || '', // Include image data for Gemini Vision analysis
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(`API error: ${errorData.error || response.statusText}`);
    }

    const result = await response.json();
    // Make sure we're using the notes field from the API response
    const notes = result.notes;
    console.log('AI-generated notes received from API:', notes);

    // Send progress update to popup
    chrome.runtime.sendMessage({
      action: 'noteGenerationProgress',
      status: 'complete',
      message: 'Notes generated successfully!',
    });

    // Save the notes to storage
    await chrome.storage.local.set({
      lastNotes: {
        content: notes,
        timestamp: Date.now(),
        ai_analysis: result.ai_analysis, // Store AI analysis data
      },
    });

    return notes;
  } catch (error) {
    console.error('Error in generateNotes:', error);

    // Send error update to popup
    chrome.runtime.sendMessage({
      action: 'noteGenerationProgress',
      status: 'error',
      message: `Error: ${error.message}`,
    });

    throw error;
  }
}

// Process OCR using Python FastAPI server
async function processOCR(imageData, options = {}) {
  try {
    // Report starting progress
    chrome.runtime.sendMessage({
      action: 'ocrProgress',
      progress: { status: 'starting', percent: 0 },
    });

    // Send the image to our FastAPI server
    const response = await fetch(`${API_BASE_URL}/api/ocr`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        image: imageData,
      }),
    });

    // Report progress
    chrome.runtime.sendMessage({
      action: 'ocrProgress',
      progress: { status: 'processing', percent: 50 },
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(`API error: ${errorData.error || response.statusText}`);
    }

    const result = await response.json();

    // Report completion
    chrome.runtime.sendMessage({
      action: 'ocrProgress',
      progress: { status: 'completed', percent: 100 },
    });

    // Return the extracted text and image data for Gemini Vision
    return {
      text: result.text || '',
      image_data: result.image_data || '',
    };
  } catch (error) {
    console.error('Error in processOCR:', error);

    // Report error
    chrome.runtime.sendMessage({
      action: 'ocrProgress',
      progress: { status: 'error', percent: 0, error: error.message },
    });

    throw error;
  }
}

// Simulate OCR processing (in real implementation, this would use Tesseract.js or a server API)
function simulateOCR(imageData) {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve(
        'Sample text extracted from the screen capture. In a real implementation, this would be actual text extracted using OCR.'
      );
    }, 1000);
  });
}

// Process speech-to-text using the backend API
function processSTT(audioData) {
  return new Promise(async (resolve, reject) => {
    try {
      // Check if audio data is valid
      if (!audioData) {
        console.warn('No audio data provided for transcription');
        resolve('');
        return;
      }

      console.log('Audio data type:', typeof audioData);
      console.log('Audio data starts with:', audioData.substring(0, 50) + '...');

      // Create a FormData object to send the audio data
      const formData = new FormData();
      try {
        const audioBlob = dataURItoBlob(audioData);
        formData.append('file', audioBlob, 'recording.mp3');
        console.log('Audio blob created successfully, size:', audioBlob.size);
      } catch (error) {
        console.error('Failed to convert audio data to blob:', error);
        resolve('');
        return;
      }
      
      formData.append('language', 'auto'); // Auto-detect language

      // Send to backend API
      const response = await fetch(`${API_BASE_URL}/api/transcribe`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`Server error (${response.status}):`, errorText);
        throw new Error(`Server responded with ${response.status}: ${errorText}`);
      }

      const data = await response.json();
      console.log('Transcription received:', data);
      resolve(data.text || '');
    } catch (error) {
      console.error('Error in speech-to-text processing:', error);
      resolve(''); // Return empty string on error
    }
  });
}

// Helper function to convert data URI to Blob
function dataURItoBlob(dataURI) {
  try {
    // Check if dataURI is valid
    if (!dataURI || typeof dataURI !== 'string') {
      console.error('Invalid data URI: not a string or empty');
      return new Blob([], { type: 'application/octet-stream' });
    }
    
    if (!dataURI.includes(',')) {
      console.error('Invalid data URI format: missing comma separator');
      console.log('Data URI prefix:', dataURI.substring(0, Math.min(50, dataURI.length)));
      return new Blob([], { type: 'application/octet-stream' });
    }
    
    const parts = dataURI.split(',');
    // Make sure we have a base64 encoded part
    if (parts.length !== 2) {
      console.error('Data URI missing base64 data');
      return new Blob([], { type: 'application/octet-stream' });
    }
    
    // Get MIME type
    let mimeString = 'application/octet-stream';
    if (parts[0].includes(':') && parts[0].includes(';')) {
      mimeString = parts[0].split(':')[1].split(';')[0];
    }
    
    // Check if it's base64 encoded
    if (!parts[0].includes('base64')) {
      console.error('Data URI is not base64 encoded');
      return new Blob([parts[1]], { type: mimeString });
    }
    
    // Decode base64
    try {
      const byteString = atob(parts[1]);
      const ab = new ArrayBuffer(byteString.length);
      const ia = new Uint8Array(ab);

      for (let i = 0; i < byteString.length; i++) {
        ia[i] = byteString.charCodeAt(i);
      }

      return new Blob([ab], { type: mimeString });
    } catch (e) {
      console.error('Failed to decode base64 data:', e);
      return new Blob([], { type: mimeString });
    }
  } catch (error) {
    console.error('Error converting data URI to Blob:', error);
    return new Blob([], { type: 'application/octet-stream' });
  }
}
