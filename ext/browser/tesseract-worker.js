// Tesseract.js worker script
importScripts('https://cdn.jsdelivr.net/npm/tesseract.js@4/dist/tesseract.min.js');

// Initialize Tesseract worker
const worker = Tesseract.createWorker();

// Listen for messages from the main thread
self.addEventListener('message', async (e) => {
  const { imageData, options } = e.data;
  
  try {
    // Initialize the worker
    await worker.load();
    await worker.loadLanguage(options.lang || 'eng');
    await worker.initialize(options.lang || 'eng');
    
    // Set recognition parameters if provided
    if (options.params) {
      await worker.setParameters(options.params);
    }
    
    // Send progress updates
    const progressCallback = (progress) => {
      self.postMessage({ type: 'progress', progress });
    };
    
    // Recognize text in the image
    const result = await worker.recognize(imageData, options, { progressCallback });
    
    // Send the result back to the main thread
    self.postMessage({
      type: 'result',
      data: result.data,
      success: true
    });
    
  } catch (error) {
    // Send error back to the main thread
    self.postMessage({
      type: 'error',
      error: error.message,
      success: false
    });
  }
});