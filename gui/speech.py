import json
from loguru import logger
from nicegui import ui


SPEECH_SUPPORT_HTML = """
<script>
(() => {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  window.__speech = window.__speech || {};
  window.__speech.supported = !!SpeechRecognition;
  window.__speech._recognition = null;
  window.__speech._resolve = null;
  window.__speech._reject = null;
  window.__speech._inputSelector = '.stt-input input';

  window.__speech._setInputValue = (value) => {
    const input = document.querySelector(window.__speech._inputSelector);
    if (!input) return;
    input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true }));
  };

  window.__speech.start = () => {
    return new Promise((resolve, reject) => {
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) {
        reject('SpeechRecognition not supported');
        return;
      }

      if (window.__speech._recognition) {
        try { window.__speech._recognition.stop(); } catch (e) { /* no-op */ }
      }

      const recognition = new SR();
      window.__speech._recognition = recognition;
      window.__speech._resolve = resolve;
      window.__speech._reject = reject;

      recognition.lang = navigator.language || 'en-US';
      recognition.interimResults = true;
      recognition.continuous = false;

      let finalTranscript = '';
      recognition.onresult = (event) => {
        let interim = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          const transcript = result[0].transcript;
          if (result.isFinal) finalTranscript += transcript;
          else interim += transcript;
        }
        const combined = (finalTranscript + ' ' + interim).trim();
        window.__speech._setInputValue(combined);
      };

      recognition.onerror = (event) => {
        const err = event.error || 'speech_recognition_error';
        if (window.__speech._reject) window.__speech._reject(err);
        window.__speech._reject = null;
        window.__speech._resolve = null;
      };

      recognition.onend = () => {
        if (window.__speech._resolve) window.__speech._resolve(finalTranscript.trim());
        window.__speech._resolve = null;
        window.__speech._reject = null;
      };

      recognition.start();
    });
  };

  window.__speech.stop = () => {
    try {
      if (window.__speech._recognition) window.__speech._recognition.stop();
    } catch (e) { /* no-op */ }
  };

  window.__speech.speak = (text) => {
    if (!('speechSynthesis' in window)) return false;
    if (!text) return false;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = navigator.language || 'en-US';
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    return true;
  };

  window.__speech.cancel = () => {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
  };
})();
</script>
"""


def init_speech_support() -> None:
    ui.add_head_html(SPEECH_SUPPORT_HTML)


async def start_listening(user_input: ui.input) -> str | None:
    try:
        result = await ui.run_javascript("return await window.__speech.start()")
    except Exception as exc:
        logger.warning(f"Speech recognition failed: {exc}")
        ui.notify(f"Speech recognition failed: {exc}", type='negative')
        return None

    if result:
        user_input.value = result
    return result


async def stop_listening() -> None:
    try:
        await ui.run_javascript("window.__speech.stop()")
    except Exception as exc:
        logger.warning(f"Failed to stop speech recognition: {exc}")


async def speak(text: str) -> None:
    try:
        payload = json.dumps(text)
        ok = await ui.run_javascript(f"return window.__speech.speak({payload})")
        if not ok:
            ui.notify("Text-to-speech is not available in this browser.", type='warning')
    except Exception as exc:
        logger.warning(f"Text-to-speech failed: {exc}")
        ui.notify(f"Text-to-speech failed: {exc}", type='negative')


async def cancel_speech() -> None:
    try:
        await ui.run_javascript("window.__speech.cancel()")
    except Exception as exc:
        logger.warning(f"Failed to cancel speech: {exc}")
