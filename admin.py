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
        if msg_entity.type == 'pre' and msg_entity.language in ('sh', 'bash', 'shell'):
            cmd = msg_entity.text(update.message)
            try:
                p = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            except Exception as e:
                traceback_string = traceback.format_exc()
                resps.append(('exception', traceback_string))
            else:
                resps.append(('process', p.returncode, p.stderr.decode(), p.stdout.decode()))

    tmpl = jinja2_env.from_string('''
{%- for r in resps %}
{%- if r[0] == "exception" %}
<pre><code class="language-python">
{{ r[1] }}
</code></pre>
{%- elif r[0] == 'process' %}
return_code: <pre>{{ r[1] }}</pre>
stdout:
<pre><code class="language-bash">
{{ r[3] }}
</code></pre>
stderr: 
<pre><code class="language-bash">
{{ r[2] }}
</code></pre>
{%- else %}
{{ r.__repr__() }}
{%- endif %}
{% else %}
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
