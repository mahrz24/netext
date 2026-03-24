from textual.timer import Timer

# Textual has a bug where Timer._run divides by _interval when _interval is 0
# (line: `count = int((now - start) / _interval + 1)`), and _stop_all only
# catches CancelledError, not ZeroDivisionError. This can happen when any code
# path creates a timer with interval 0 via set_timer(0, ...).
#
# Upstream issue: https://github.com/Textualize/textual/issues/6370
_original_stop_all = Timer._stop_all.__func__


@classmethod
async def _safe_stop_all(cls, timers):
    try:
        await _original_stop_all(cls, timers)
    except ZeroDivisionError:
        pass


Timer._stop_all = _safe_stop_all
