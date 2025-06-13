# -- начало прежнего кода опущен --
# вот та строка с фиксами:
@dp.message(F.text == "/help")
async def cmd_help(msg: Message):
    if msg.chat.id == CHAT_ID:
        await msg.answer("""🛠 Команды:
/ping
/status
/pause
/resume
/threshold 0.002
/list
/log""")
# -- остальной код остался прежним --
