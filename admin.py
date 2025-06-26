import contextlib
import os
import sys
from datetime import datetime
from pathlib import Path
import functools as FT, itertools as IT, operator as OP
import io

import subprocess
import traceback

import jinja2

from telegram import telegram


jinja2_env = jinja2.Environment()
jinja2_env.globals['now'] = datetime.now()


def admin_exec(bot, update):
    if update.message.from_.id != update.message.chat.id or update.message.from_.id != 507902673:
        # not emitting any message to avoid being detected
        return

    resps = []
    for msg_entity in update.message.entities:
        if msg_entity.type == 'pre':
            if msg_entity.language in ('sh', 'bash', 'shell', None):
                cmd = msg_entity.text(update.message)
                import send_message
                env = dict(os.environ,
                           SEND_MESSAGE=f'{sys.executable} {send_message.__file__}',
                           BOT_API_TOKEN=bot._api_token,
                           UPDATE_ID=str(update.id),
                           CHAT_ID=str(update.message.chat.id),
                           REPLY_TO_MESSAGE_ID=str(update.message.id),
                           )
                try:
                    p = subprocess.run(cmd, shell=True,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       timeout=60, env=env,
                                       )
                except Exception as e:
                    traceback_string = traceback.format_exc()
                    resps.append(('exception', traceback_string))
                else:
                    resps.append(('process', p.returncode, p.stderr.decode(), p.stdout.decode()))
            elif msg_entity.language in ('python', 'python3'):
                cmd = msg_entity.text(update.message)
                stderr = io.StringIO()
                stdout = io.StringIO()
                with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(stdout):
                    try:
                        exec(cmd)
                    except Exception as e:
                        traceback_string = traceback.format_exc()
                        resps.append(('exception', traceback_string))
                    else:
                        resps.append(('python', stderr.getvalue(), stdout.getvalue()))


    tmpl = jinja2_env.from_string('''
{%- for r in resps %}
{%- if r %}
---------------------------
#{{ loop.index0 }} <code>{{ r[0] }}</code> block:
{%- endif %}
{%- if r[0] == "exception" %}
<pre><code class="language-python">{{ r[1]|e }}</code></pre>
{%- elif r[0] == 'process' %}
return_code: <code>{{ r[1] }}</code>
{%- if r[3].strip() %}
stdout:
<pre><code class="language-bash">{{ r[3]|e }}</code></pre>
{%- endif %}
{%- if r[2].strip() %}
stderr: 
<pre><code class="language-bash">{{ r[2]|e }}</code></pre>
{%- endif %}
{%- elif r[0] == 'python' %}
{%- if r[2].strip() %}
stdout:
<pre><code class="language-python">{{ r[2]|e }}</code></pre>
{%- endif %}
{%- if r[1].strip() %}
stderr: 
<pre><code class="language-python">{{ r[1]|e }}</code></pre>
{%- endif %}
{%- else %}
{{ r.__repr__()|e }}
{%- endif %}
{%- else %}
*nothing to execute*
{%- endfor %}
''')
    text = tmpl.render(resps=resps)
    try:
        return bot.send_message(
            chat=update.message.chat,
            reply_to_message=update.message,
            text=text,
            parse_mode=telegram.Message.ParseMode.HTML,
        )
    except telegram.MessageTooLong:
        with io.StringIO(text) as file:
            file.name = 'resp.html'
            return bot.send_document(
                update.message.chat,
                caption=f'Message too long, sent as file',
                document=file,
                reply_to_message=update.message,
            )


def admin_upload(bot, update):
    if update.message.from_.id != update.message.chat.id or update.message.from_.id != 507902673:
        # not emitting any message to avoid being detected
        return

    reply = FT.partial(bot.send_message, chat=update.message.chat, reply_to_message=update.message)

    cmd_arg = update.message.bot_command_argument
    if not cmd_arg:
        return reply(
            text='/upload cmd requires argument (filepath)',
        )

    FORCE_OPTS = {'-f', '--force'}
    cmd_arg_parts = cmd_arg.split()
    forced = FORCE_OPTS.intersection(cmd_arg_parts)

    # todo: why such tolerancy here, just require it to be at start or end of filepath argument
    if forced:
        cmd_arg = ' '.join(p for p in cmd_arg_parts if p not in {'-f', '--force'})

    p = Path(cmd_arg.strip())
    if p.exists() and not forced:
        return reply(
            text='File already exists, can not overwrite it (add -f/--force to bypass)',
        )

    file_type = None

    if update.message.document:
        file_type = 'document'
        p.write_bytes(bot.file(update.message.document.file_id))
    elif update.message.photo:
        file_type = 'photo'
        max_size_photo_file_id = max(update.message.photo, key=OP.attrgetter('file_size')).file_id
        p.write_bytes(bot.file(max_size_photo_file_id))
    elif update.message.video:
        file_type = 'video'
        p.write_bytes(bot.file(update.message.video.file_id))
    else:
        return reply(text='*todo*: file not found on update.message!')

    return reply(
        text=f'File ({file_type}) saved to {p}',
    )


def admin_download(bot, update):
    if update.message.from_.id != update.message.chat.id or update.message.from_.id != 507902673:
        # not emitting any message to avoid being detected
        return

    reply = FT.partial(bot.send_message, chat=update.message.chat, reply_to_message=update.message)

    cmd_arg = update.message.bot_command_argument
    if not cmd_arg:
        return reply(
            text='/upload cmd requires argument (filepath)',
        )

    p = Path(cmd_arg.strip())
    if not p.exists():
        return reply(
            text='File not found',
        )

    bot.send_chat_action(update.message.chat, telegram.Chat.Action.UPLOAD_DOCUMENT)

    with p.open('rb') as file:
        return bot.send_document(
            update.message.chat,
            caption=f'<pre><code>{subprocess.run(["ls", "-ahl", str(p)], stdout=subprocess.PIPE).stdout.decode().strip()}</code></pre>',
            document=file,
            parse_mode=telegram.Message.ParseMode.HTML,
            reply_to_message=update.message,
        )
