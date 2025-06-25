import time
import itertools as IT, functools as FT, operator as OP  # noqa: F401, E401
from typing import Optional

from telegram import telegram
import traceback

from datetime import datetime, timedelta
import logging

import config
import json

logger = logging.getLogger(__name__)
logger.setLevel(config.LOGLEVEL)


class StringifyJSONEncoder(json.JSONEncoder):
    def default(self, o):
        class_name = str(type(o)).replace('<', '{').replace('>', '}')
        return f'{class_name}: {o}'


def split_to_chunks(data, size):
    for i in range(0, len(data), size):
        yield data[i:i + size]


def _report_message(bot, text, **send_msg_kwargs):
    if config.REPORT_CHAT_ID:
        bot.send_message(chat=config.REPORT_CHAT_ID, text=text, **send_msg_kwargs)
    else:
        logger.info('_report_message() called, but no REPORT_CHAT_ID found (%r, %r, %r)', bot, text, send_msg_kwargs)


class Handler:
    def can_handle(self, bot, update) -> bool:
        raise NotImplementedError()

    def handle(self, bot, update):
        raise NotImplementedError()


class BotCommandHandler(Handler):
    def __init__(self, bot_command, func):
        assert bot_command
        self.bot_command = bot_command
        self.func = func

    @staticmethod
    def _get_bot_command(update):
        if update.type == telegram.Update.Type.MESSAGE:
            return update.message.bot_command

    def can_handle(self, bot, update):
        return self._get_bot_command(update) == self.bot_command

    def handle(self, bot, update):
        return self.func(bot, update)


def main(repeating_tracebacks={}):
    # repeating_tracebacks = dict()

    if config.DEBUG:
        logging.basicConfig(level=config.LOGLEVEL)

    bot = telegram.Bot.by(token=config.BOT_API_TOKEN)

    _report_message(bot, ':: *bot restarted*', parse_mode=telegram.Message.ParseMode.MARKDOWN_V2)

    import admin

    handlers = [
        BotCommandHandler('/_admin_exec', admin.admin_exec),
        BotCommandHandler('/_admin_upload', admin.admin_upload),
        BotCommandHandler('/_admin_download', admin.admin_download),
        BotCommandHandler('/start', lambda b, u: b.send_message(text='Hello, world!', chat=u.message.chat)),
    ]

    update: Optional[telegram.Update] = None
    while True:
        logger.debug('sleeping...')
        time.sleep(1)
        try:
            updates = bot.updates(after=update, timeout=config.GET_UPDATES_TIMEOUT)
            if not updates:
                continue

            for update in updates:
                bot_command = BotCommandHandler._get_bot_command(update)
                if bot_command is False:
                    continue

                if update.type not in (telegram.Update.Type.MESSAGE, ) \
                        or (update.message.pinned_message is not None):
                    logger.warning("TODO: handle %r", update)
                    continue

                for handler in handlers:
                    handler_args = bot, update
                    if handler.can_handle(*handler_args):
                        handler.handle(*handler_args)
                        break
                else:
                    bot.send_message(
                        text='unknown type of message',
                        chat=update.message.chat,
                        reply_to_message=update.message,
                    )
        except KeyboardInterrupt:
            raise
        except:  # noqa: E722
            traceback.print_exc()
            if config.REPORT_CHAT_ID:
                traceback_string = traceback.format_exc()
                ts = datetime.now()
                if traceback_string not in repeating_tracebacks \
                        or ts - repeating_tracebacks[traceback_string] > timedelta(hours=1):
                    traceback.print_exc()
                    repeating_tracebacks[traceback_string] = ts
                    to_json = FT.partial(json.dumps, cls=StringifyJSONEncoder)

                    def recursively_remove_nones(d):
                        if isinstance(d, dict):
                            return {k: recursively_remove_nones(v) for k, v in d.items() if v not in (None, [], {})}
                        if isinstance(d, list):
                            return [recursively_remove_nones(i) for i in d]
                        return d

                    update_json = (last_update := locals().get('update')) and to_json(
                        recursively_remove_nones(telegram.attr.asdict(last_update))
                    )
                    from textwrap import dedent
                    tmpl = admin.jinja2_env.from_string('''\
Some error occured on bot:
<pre><code class="language-python">
{{ traceback_string|e }}
</code></pre>
Update serialized:
<pre><code class="json">
{{ update_json }}
</code></pre>
Last response:
<pre><code class="json">
{{ last_response }}
</code></pre>
''')
                    text = tmpl.render(traceback_string=traceback_string,
                                       update_json=update_json,
                                       last_response=bot._last_response and to_json(bot._last_response))
                    _report_message(bot, text, parse_mode=telegram.Message.ParseMode.HTML)
                else:
                    logger.info('not sending same traceback')
            logger.info('sleeping after error...')
            time.sleep(30)


if __name__ == '__main__':
    while True:
        try:
            main()
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:  # noqa: E722
            traceback.print_exc()
            time.sleep(60)
