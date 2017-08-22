"""
A requests-based Server-sent Events client implementation
"""

import requests
import time


def stream_raw_sse(mkrequest, *pargs, _last_event_id=None, headers=None, **kwargs):
    """
    Streams Server-Sent Events, each event produced as a sequence of
    (field, value) pairs.

    Does not handle reconnection, etc.
    """
    if headers is None:
        headers = {}
    headers['Accept'] = 'text/event-stream'
    headers['Cache-Control'] = 'no-cache'
    # Per https://html.spec.whatwg.org/multipage/server-sent-events.html#sse-processing-model
    if _last_event_id is not None:
        headers['Last-Event-ID'] = _last_event_id

    with mkrequest(*pargs, headers=headers, stream=True, **kwargs) as resp:
        fields = []
        for line in resp.iter_lines(decode_unicode=True):
            # https://html.spec.whatwg.org/multipage/server-sent-events.html#event-stream-interpretation
            if not line:
                yield fields
                fields = []
            elif line.startswith(':'):
                pass
            elif ':' in line:
                field, value = line.split(':', 1)
                if value.startswith(' '):
                    value = value[1:]
                fields += [(field, value)]
            else:  # Non-blank, without a colon
                fields += [(line, '')]


def stream_sse(mkrequest, *pargs, **kwargs):
    """
    Streams server-sent events, producing a dictionary of the fields.

    Handles reconnecting, Last-Event-ID, and retry waits.

    Deviates by spec by passing through unknown fields instead of ignoring them.
    If an unknown field is given more than once, the last given wins (like
    event and id).
    """
    retry = 0
    last_id = None
    while True:
        try:
            for rawmsg in stream_raw_sse(mkrequest, *pargs, _last_event_id=last_id, **kwargs):
                msg = {'event': 'message', 'data': ''}
                # https://html.spec.whatwg.org/multipage/server-sent-events.html#event-stream-interpretation
                for k, v in rawmsg:
                    if k == 'retry':
                        try:
                            retry = int(v)
                        except ValueError:
                            pass
                    elif k == 'data':
                        if msg['data']:
                            msg['data'] += '\n' + v
                        else:
                            msg['data'] = v
                    else:
                        if k == 'id':
                            last_id = v
                        # Spec says we should ignore unknown fields. We're passing them on.
                        msg[k] = v
                if not msg['data']:
                    pass
                yield msg
            else:
                raise StopIteration  # Really just exists to get caught in the next line
        except (StopIteration, requests.RequestException, EOFError):
            # End of stream, try to reconnect
            # NOTE: GeneratorExit is thrown if the consumer kills us (or we get GC'd)
            # TODO: Log something?

            # Wait, fall through, and start at the top
            time.sleep(retry / 1000)
