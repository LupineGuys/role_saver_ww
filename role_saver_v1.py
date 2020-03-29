import logging
import re
import time
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram.ext.dispatcher import run_async
from telegram.utils.helpers import mention_html as mention

MY_AWESOME_TOKEN = ""

admins = [951153044]
bot_list = [
    175844556, 198626752,  # ww moderator, ww moderator beta
    618096097, 1029642148  # black ww, black ww 2
]

in_game_users = {}  # to save in game users in different groups
allow_users = {}  # to save allow users in different groups
roles = {}  # to save roles in different groups
rules = {}  # to save rules in different groups
block_list = {}  # to save banned users in different groups
used_messages = {}  # to save messages to dont use them twice in different groups
ask_roles = {}  # to save count asked roles per game days in different groups
leader = {}  # to save game leader in different groups

game_finish = r'طول مدت بازی|مدت زمان بازی|مدت بازی|مدت بُکُن بُکُن'
game_list = r'بازیکن های زنده|فراموشکارای زنده|هنرمندای فعال|دانشجوهای مشغول به تحصیل|مسافرای زنده ی توی قطار|بازیکنان زنده|بازیکن های آنلاین|کونده های زنده |بازیکنان درحال بازی|برره ای های زنده|مسافر های زنده:|کشتی گیران سالم|هیولاهای زنده|بازمانده ها'
death = r'مرده|اخراج شده|کنار رفته|آفلاین|تبعید شده|بگا رفته|خارج شده|سقَط شده|فرار کرده|اخراج شده|نفله وشده'


def check_chat(func):
    def check_in_in_game_users(chat_id):
        global in_game_users
        if chat_id not in in_game_users:
            in_game_users.update({chat_id: []})

    def check_in_allow_users(chat_id):
        global allow_users
        if chat_id not in allow_users:
            allow_users.update({chat_id: []})

    def check_in_used_messages(chat_id):
        global used_messages
        if chat_id not in used_messages:
            used_messages.update({chat_id: set({})})

    def check_in_roles(chat_id):
        global roles
        if chat_id not in roles:
            roles.update({chat_id: {}})

    def check_in_rules(chat_id):
        global rules
        if chat_id not in rules:
            rules.update({chat_id: {
                'save_your_role': True,
                'save_role': True,
                'leader_status': True
            }})

    def check_in_ask_roles(chat_id):
        global ask_roles
        if chat_id not in ask_roles:
            ask_roles.update({chat_id: 0})

    def check_in_leader(chat_id):
        global leader
        if chat_id not in leader:
            leader.update({chat_id: None})

    def wrapper_check(update, context):
        chat = update.effective_chat
        user = update.effective_user

        check_in_in_game_users(chat.id)
        check_in_allow_users(chat.id)
        check_in_used_messages(chat.id)
        check_in_roles(chat.id)
        check_in_rules(chat.id)
        check_in_ask_roles(chat.id)
        check_in_leader(chat.id)

        func(update, context)

    return wrapper_check


def check_status(func):
    global block_list

    def check_chat_in_ban_list(chat_id):
        if chat_id not in block_list:
            block_list.update({chat_id: []})

    def check_user_in_ban_list(chat_id, user_id):
        if user_id in block_list[chat_id]:
            return True
        return False

    def wrapper_check(update, context):
        chat = update.effective_chat
        user = update.effective_user

        check_chat_in_ban_list(chat.id)

        status = check_user_in_ban_list(chat.id, user.id)
        if status:
            return

        func(update, context)

    return wrapper_check


def check_admin(_func=None, *, reply_enabled=False):
    def wrapper_check_(func):
        def wrapper_check_admin(update, context):
            chat = update.effective_chat
            user = update.effective_user

            user = bot.get_chat_member(chat_id=chat.id, user_id=int(user.id))
            if user.status == 'creator' or user.status == 'administrator' or user.user.id in admins:
                func(update, context)
                return

            if reply_enabled:
                update.message.reply_text('ادمین نیستی')

        return wrapper_check_admin

    if _func is None:
        return wrapper_check_
    else:
        return wrapper_check_(_func)


def start(update, context):
    context.bot.send_message(update.message.chat_id, "hey, unfortunately i do nothing here for you :( ")
    pass


@run_async
@check_chat
@check_status
def update_list(update, context):
    user = update.message.from_user
    chat = update.message.chat

    # check message is replied to game bot
    if not update.message.reply_to_message or update.message.reply_to_message.from_user.id not in bot_list:
        update.message.reply_text('به لیست بازی ربات ریپلای بزنید')  # reply to game list
        return
    # check game list is not used before
    if update.message.reply_to_message.message_id in used_messages[chat.id]:
        update.message.reply_text('این لیست قبلا ثبت شده است')  # list used before
        return

    message_text = update.message.reply_to_message.text  # game message
    entities = update.message.reply_to_message['entities']  # entities list

    global allow_users, in_game_users, ask_roles, roles

    # check if this message is the last list of the game
    if re.search(game_finish, message_text):
        context.bot.send_message(chat.id, 'بازی خوبی بود')  # gg
        roles.update({chat.id: {}})  # clean roles list
        allow_users.update({chat.id: {}})  # clean player list
        return

    # check if this is game middle list
    elif re.search(death, message_text):
        # list alive players (died players are not mentioned in list)
        alive_users = [ent['user'].id for ent in entities if ent['type'] == 'text_mention']

        # update allowed users to save role
        allow_users[chat.id] = alive_users
        # reset ask role status
        ask_roles[chat.id] = 0
        # add message id into used messages
        used_messages[chat.id].add(update.message.message_id)

        context.bot.send_message(chat.id, 'لیست اپدیت شد')  # role list updated

        saved_roles = roles[chat.id]  # roles list
        allow_players = allow_users[chat.id]  # alive players

        msg = "لیست نقش های ثبت شده \n\n"  # list of saved roles

        # get leader
        leader_id = leader[chat.id]
        if leader_id in allow_players:
            leader_user_obj = bot.get_chat_member(chat_id=chat.id, user_id=int(leader_id))
            msg += "شکارچی : {}\n".format(mention(leader_id, leader_user_obj.user.first_name))

        #  if any role saved
        if not saved_roles:

            # check if leader exists
            if leader_id:
                context.bot.send_message(chat.id, msg, parse_mode='HTML')
                return

            msg = "هیشکی نقششو ثبت نکرده 😐 \n"  # anyone saved role

            # check group rules for response
            group_rules = rules[chat.id]
            if group_rules:
                if group_rules['save_your_role']:
                    msg += 'با /saveYourRole ازشون ک نقششونو بپرسید'  # ask with ask role
                elif group_rules['save_role']:
                    msg += 'با /sn نقش خودتونو ثبت کنید'  # save with /sn
                else:
                    msg = ""
            # if no setting modified
            else:
                msg += 'با /saveYourRole ازشون ک نقششونو بپرسید'

        # list alive roles
        for player in saved_roles:
            # check player is not alive
            if player not in allow_players:
                continue
            # check player is leader
            if player == leader_id:
                continue

            player_obj = bot.get_chat_member(chat_id=chat.id, user_id=int(player))
            name = player_obj.user.full_name
            msg += f'{name} : {saved_roles[player]}\n'

        context.bot.send_message(chat.id, msg, parse_mode='HTML')
        return

    elif re.search(game_list, message_text):
        # list alive players (died players are not mentioned in list)
        alive_users = [ent['user'].id for ent in entities if ent['type'] == 'text_mention']

        # update allowed users to save role and in game users
        allow_users[chat.id] = alive_users
        in_game_users[chat.id] = alive_users
        # reset ask role status
        ask_roles[chat.id] = 0
        # add message id into used messages
        used_messages[chat.id].add(update.message.reply_to_message.message_id)

        # check group rules for response
        group_rules = rules[chat.id]
        msg = f'با {len(alive_users)} بازیکن بازی شروع شد\n'
        if group_rules:
            if group_rules['save_your_role']:
                msg += ' برای اینکه نقش اون هارو بخاهید از دستور /saveYourRole استفاده کنید'  # ask with ask role
            elif group_rules['saverole']:
                msg += 'با /sn نقش خودتونو ثبت کنید'  # save with /sn
            else:
                pass
        else:
            msg += ' برای اینکه نقش اون هارو بخاهید از دستور /saveYourRole استفاده کنید'

        context.bot.send_message(chat.id, msg)
        return
    else:
        context.bot.send_message(chat.id, 'seems its not a game list message')


@run_async
@check_chat
@check_status
def set_rule(update, context):
    user = update.message.from_user
    chat = update.message.chat

    # check save role is disabled
    group_rules = rules[chat.id]
    if not group_rules['save_role']:
        update.message.reply_text('امکان استفاده از این دستور غیر فعال است')
        return

    if update.message.reply_to_message:
        # return because in most of the times its its a simple remind
        return

    allowed_users = allow_users[chat.id]
    all_players = in_game_users[chat.id]

    # check if any game is playing
    if not all_players:
        update.message.reply_text('بازی ای در جریان نیست\n یدونه شروع کن')
        return

    # check user is alive
    if user.id in allowed_users:
        global roles

        role = ' '.join(context.args)

        # if role is empty
        if not role:
            update.message.reply_text('فوت نکن')  # dont blow
            return

        # save role
        roles[chat.id].update({user.id: role.replace('\n', ' ')})
        update.message.reply_text('نقشت ثبت شد')
        return

    # check user died
    elif user.id not in allowed_users and user.id in all_players:
        update.message.reply_text('چک کن ببین انگار مردی')
        return

    # check user in game
    elif user.id not in allowed_users:
        update.message.reply_text('تو بازی نیستی ک')
        return


@run_async
def set_leader(update, context):
    """nothing yet"""


@run_async
def set_vote(update, context):
    """nothing yet"""


@run_async
def say_vote(update, context):
    """nothing yet"""


@run_async
@check_chat
@check_status
@check_admin(reply_enabled=True)
def block(update, context):
    global block_list
    chat = update.message.chat
    user = update.message.from_user

    #  check command replied to some one
    if not update.message.reply_to_message:
        update.message.reply_text('ریپلای بزن')  # reply to someone
        return

    target = update.message.reply_to_message.from_user
    # check if banned before
    if target.id in block_list[chat.id]:
        update.message.reply_text('این یتیم و قبلا یکی دیگه بنش کرده ولش کن')  # user blocked before
        return

    # add to ban list of group
    block_list[chat.id].append(target.id)
    update.message.reply_text(
        'با موفقیت مسدود شد\n دیگه نمیتونه توی این گروه از هیچ دستوری استفاده کنه'  # user successfully blocked
    )


@run_async
@check_chat
@check_status
@check_admin(reply_enabled=True)
def unblock(update, context):
    global block_list
    chat = update.message.chat_id
    user = update.message.from_user

    #  check command replied to some one
    if not update.message.reply_to_message:
        update.message.reply_text('ریپلای بزن')  # reply to someone
        return

    target = update.message.reply_to_message.from_user
    # check if not blocked before
    if target.id not in block_list[chat.id]:
        update.message.reply_text('بچه خوبیه مسدود نیسش')  # user not blocked before
        return

    # remove from block list of group
    block_list[chat.id].append(target.id)
    update.message.reply_text(
        'از مسدودیت بیرون اومد'  # user successfully unblocked
    )


@run_async
@check_chat
@check_status
@check_admin
def delete_role(update, context):
    global roles
    user = update.message.from_user
    chat = update.message.chat

    # check user has not set role
    if user.id not in roles[chat.id]:
        update.message.reply_text('نقشی ثبت نشده بود از این بازیکن')  # user has not set role

    # remove user role
    roles[chat.id].pop(user.id)
    update.message.reply_text('باش')  # okay


@run_async
def my_state(update, context):
    """when converted to db"""


@run_async
def group_state(update, context):
    """when converted to db"""


@run_async
@check_chat
@check_status
def save_your_role(update, context):
    user = update.message.from_user
    chat = update.message.chat

    # check ask role is allow
    group_rules = rules[chat.id]
    if group_rules:
        if not group_rules['save_your_role']:
            update.message.reply_text('امکان استفاده از این دستور غیر فعال است')  # this option is disabled
            return

    # if ask role is used before in this game day
    if ask_roles[chat.id] >= 1:
        update.message.reply_text("شما تنها یک بار در هر روز میتوانید درخواست نقش کنید")

    # set ask role used one time in this group
    ask_roles[chat.id] += 1

    allowed_users = allow_users[chat.id]
    saved_roles = roles[chat.id]

    # if no one alive
    if not group_rules['save_your_role']:
        update.message.reply_text('امکان استفاده از این دستور غیر فعال است')  # this option is disabled
        return

    # list of users who have not saved role
    not_saved_role_users = [user for user in allowed_users if user not in saved_roles]

    # ask role if there are anyone have not saved role
    for user in not_saved_role_users:
        user_obj = bot.get_chat_member(chat_id=chat.id, user_id=int(user))
        name = user_obj.user.full_name
        context.bot.send_message(chat.id,
                                 text="""{} نقشت چیه ؟""".format(mention(user, name)),  # what is your role ?
                                 parse_mode='HTML')
        time.sleep(1)
    msg = f'ببین نقش این {len(not_saved_role_users)}‏ نفر چیه'  # look what is their role

    # check if all users have saved a role
    if not not_saved_role_users:
        msg = 'بچه های خوبی دارید همشون نقشاشونو ثبت کردن 😅'  # every body saved a role

    update.message.reply_text(msg)


@run_async
@check_chat
@check_status
def role_list(update, context):
    user = update.message.from_user
    chat = update.message.chat

    msg = "لیست نقش های ثبت شده \n\n"  # saved role list

    saved_roles = roles[chat.id]
    allowed_players = allow_users[chat.id]

    # get leader
    leader_id = leader[chat.id]
    if leader_id in allowed_players:
        user_obj = bot.get_chat_member(chat_id=chat.id, user_id=int(leader_id))
        msg += "شکارچی : {}\n".format(mention(leader_id, user_obj.user.first_name))

    # list alive roles
    for player in saved_roles:
        # check player is not alive
        if player not in allowed_players:
            continue
        # check player is leader
        if player == leader_id:
            continue

        player_obj = bot.get_chat_member(chat_id=chat.id, user_id=int(player))
        name = player_obj.user.full_name
        msg += f'{mention(player, name)} : {saved_roles[player]}\n'

    # if anyone have not save role
    if not saved_roles:
        msg = "هیشکی نقششو ثبت نکرده 😐 \n با /saveYourRole ازشون بخواه ک نقششونو ثبت بکنن"  # ask role
    context.bot.send_message(chat.id, msg,
                             parse_mode='HTML')


@run_async
@check_chat
@check_status
def save_role_reply(update, context):
    chat = update.message.chat
    user = update.message.from_user

    print(update.message.reply_to_message.from_user.id)
    print(bot.id)
    if update.message.reply_to_message.from_user.id == bot.id:
        entities = update.message.reply_to_message['entities']

        # if find ask word is in bot message
        if update.message.reply_to_message.text.find('نقشت چیه ؟') != -1:
            mentioned_users = [ent['user'].id for ent in entities if ent['type'] == 'text_mention']

            if user.id in mentioned_users:
                global roles
                role = update.message.text

                # save role
                roles[chat.id].update({user.id: role.replace('\n', ' ')})
                update.message.reply_text('نقشت ثبت شد')


@run_async
@check_admin
@check_chat
@check_status
def setting(update, context):
    chat = update.message.chat
    group_rules = rules[chat.id]

    save_your_role = group_rules['save_your_role']
    if save_your_role:
        save_your_role_title = "فعال✅"
    else:
        save_your_role_title = "غیر فعال❌"
    save_role = group_rules['save_role']
    if save_role:
        save_role_title = "فعال✅"
    else:
        save_role_title = "غیر فعال❌"
    leader_status = group_rules['leader_status']
    if leader_status:
        leader_status_title = "فعال✅"
    else:
        leader_status_title = "غیر فعال❌"
    buttons = [
        [InlineKeyboardButton(f"{leader_status_title}",
                              callback_data=f'setting set leader_status {chat.id} {not leader_status}'),
         InlineKeyboardButton("شکارچی💂‍♂️",
                              callback_data=f'setting info leader_status')],
        [InlineKeyboardButton(f"{save_your_role_title}",
                              callback_data=f'setting set save_your_role {chat.id} {not save_your_role}'),
         InlineKeyboardButton("🔥/saveYourRole",
                              callback_data=f'setting info save_your_role')],
        [InlineKeyboardButton(f"{save_role_title}",
                              callback_data=f'setting set save_role {chat.id} {not save_role}'),
         InlineKeyboardButton("ثبت نقش🙂",
                              callback_data=f'setting info save_role')],
        [InlineKeyboardButton(f"🔷 ѕυp cнαɴɴel 🔸",
                              url='https://t.me/lupine_guys')],
        [InlineKeyboardButton(f"بستن منو",
                              callback_data='setting close')]
    ]
    context.bot.send_message(
        chat.id,
        '''به پنل مدیریتی ربات خوش آمدید👋
        روی دکمه های ردیف سمت راست کلیک کنید تا کاربرد هر دکمه را مشاهده نمایید😉''',
        reply_markup=InlineKeyboardMarkup(buttons)
    )


@run_async
@check_chat
@check_status
@check_admin
def setting_buttons(update, context):
    global rules
    query = update.callback_query
    chat = query.message.chat
    user = query.from_user
    data = query.data
    data = data.replace('setting ', '')
    if data.find('info') == 0:
        data = data.replace('info ', '')
        info = ""
        if data == 'save_your_role':
            info = "امکان پرسیدن نقش بازیکنان توسط ربات🤖"
        elif data == 'save_role':
            info = "امکان ثبت نقش برای کاربران🙂"
        elif data == 'leader_status':
            info = "امکان تعیین شکارچی بازی توسط ادمین💂‍♂️✨"
        query.answer(text=info, show_alert=True)

    elif data.find('set') == 0:
        data = data.replace('set ', '')
        data = data.split(' ')
        subject = data[0]
        group_id = data[1]
        cmd = data[2]
        if subject == 'save_your_role':
            if cmd == 'True':
                rules[int(group_id)].update({subject: True})
            if cmd == 'False':
                rules[int(group_id)].update({subject: False})

        elif subject == 'save_role':
            if cmd == 'True':
                rules[int(group_id)].update({subject: True})
            if cmd == 'False':
                rules[int(group_id)].update({subject: False})

        elif subject == 'leader_status':
            if cmd == 'True':
                rules[int(group_id)].update({subject: True})
            if cmd == 'False':
                rules[int(group_id)].update({subject: False})

        group_rules = rules[chat.id]
        save_your_role = group_rules['save_your_role']
        if save_your_role:
            save_your_role_title = "فعال✅"
        else:
            save_your_role_title = "غیر فعال❌"
        save_role = group_rules['save_role']
        if save_role:
            save_role_title = "فعال✅"
        else:
            save_role_title = "غیر فعال❌"
        leader_status = group_rules['leader_status']
        if leader_status:
            leader_status_title = "فعال✅"
        else:
            leader_status_title = "غیر فعال❌"
        buttons = [
            [InlineKeyboardButton(f"{leader_status_title}",
                                  callback_data=f'setting set leader_status {chat.id} {not leader_status}'),
             InlineKeyboardButton("شکارچی💂‍♂️",
                                  callback_data=f'setting info leader_status')],
            [InlineKeyboardButton(f"{save_your_role_title}",
                                  callback_data=f'setting set save_your_role {chat.id} {not save_your_role}'),
             InlineKeyboardButton("🔥/saveYourRole",
                                  callback_data=f'setting info save_your_role')],
            [InlineKeyboardButton(f"{save_role_title}",
                                  callback_data=f'setting set save_role {chat.id} {not save_role}'),
             InlineKeyboardButton("ثبت نقش🙂",
                                  callback_data=f'setting info save_role')
             ], [InlineKeyboardButton(f"🔷 ѕυp cнαɴɴel 🔸",
                                      url='https://t.me/lupine_guys')]
            , [InlineKeyboardButton(f"بستن منو",
                                    callback_data='setting close')]
        ]
        query.edit_message_text(
            '''به پنل مدیریتی ربات خوش آمدید👋
            روی دکمه های ردیف سمت راست کلیک کنید تا کاربرد هر دکمه را مشاهده نمایید😉''',
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.find('close') == 0:
        group_rules = rules[chat.id]
        save_your_role = group_rules['save_your_role']
        if save_your_role:
            save_your_role_title = "فعال✅"
        else:
            save_your_role_title = "غیر فعال❌"
        save_role = group_rules['save_role']
        if save_role:
            save_role_title = "فعال✅"
        else:
            save_role_title = "غیر فعال❌"
        leader_status = group_rules['leader_status']
        if leader_status:
            leader_status_title = "فعال✅"
        else:
            leader_status_title = "غیر فعال❌"
        buttons = [
            [InlineKeyboardButton(f"🔷 ѕυp cнαɴɴel 🔸", url='https://t.me/lupine_guys')]
        ]
        query.edit_message_text(
            '''
‏شکارچی💂‍♂️ : {}
‏saveYourRole🔥 : {}
‏ثبت نقش🙂 : {}

تنظیمات ثبت شد
'''.format(leader_status_title, save_your_role_title, save_role_title),
            reply_markup=InlineKeyboardMarkup(buttons)
        )


logger = logging.getLogger(__name__)


@run_async
def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def main():
    u = Updater(token=MY_AWESOME_TOKEN, use_context=True
                )
    global bot
    bot = u.bot
    dp = u.dispatcher

    dp.add_handler(CommandHandler('start', start, filters=Filters.private))
    dp.add_handler(CommandHandler('up', update_list, filters=Filters.group))
    dp.add_handler(CommandHandler('sn', set_rule, filters=Filters.group))
    dp.add_handler(CommandHandler('li', role_list, filters=Filters.group))
    dp.add_handler(CommandHandler('dl', delete_role, filters=Filters.group))
    dp.add_handler(CommandHandler('block', block, filters=Filters.group))
    dp.add_handler(CommandHandler('unblock', unblock, filters=Filters.group))
    dp.add_handler(CommandHandler('saveyourrole', save_your_role, filters=Filters.group))
    dp.add_handler(MessageHandler(Filters.reply, save_role_reply))
    dp.add_handler(CommandHandler('setting', setting, filters=Filters.group))
    dp.add_handler(CallbackQueryHandler(setting_buttons, pattern=r'^setting'))

    dp.add_error_handler(error)
    print(1)
    u.start_polling()
    u.idle()


if __name__ == '__main__':
    main()
