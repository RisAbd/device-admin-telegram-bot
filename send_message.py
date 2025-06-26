#!/usr/bin/env python3

import optparse
from telegram import telegram
from decouple import config


def main():
    p = optparse.OptionParser()
    p.add_option('-t', '--token', dest='bot_api_token', default=None)
    p.add_option('-d', '--chat-id', dest='chat_id', type='int', default=None)
    p.add_option('--text', dest='text', default=None)
    p.add_option('-u', '--update-id', dest='update_id', type='int', default=None)
    p.add_option('-r', '--reply-to-message-id', dest='reply_to_message_id', type='int', default=None)

    opts, args = p.parse_args()

    text = ' '.join(args).strip() or opts.text
    if not text:
        raise SystemExit('Text argument(s) required')

    from config import BOT_API_TOKEN, REPORT_CHAT_ID
    opts.bot_api_token = opts.bot_api_token if opts.bot_api_token is not None else config('BOT_API_TOKEN', cast=str, default=BOT_API_TOKEN)
    opts.chat_id = opts.chat_id if opts.chat_id is not None else config('CHAT_ID', cast=int, default=REPORT_CHAT_ID)
    opts.update_id = opts.update_id if opts.update_id is not None else config('UPDATE_ID', cast=int, default=0) or None
    opts.reply_to_message_id = opts.reply_to_message_id if opts.reply_to_message_id is not None else config('REPLY_TO_MESSAGE_ID', cast=int, default=0) or None

    bot = telegram.Bot.by(token=opts.bot_api_token)
    bot.send_message(
        text=text,
        chat=opts.chat_id,
        reply_to_message=opts.reply_to_message_id,
    )


if __name__ == '__main__':
    main()
