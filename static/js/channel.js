var channel = {
    username: null,
    soundEnabled: true,

    init: function() {
        channel.username = $('meta[name="username"]').attr('content');
        channel.initChannels();
        channel.initSound();
    },

    initChannel: function(token) {
        if (token) {
            var new_channel = new goog.appengine.Channel(token);
            var socket = new_channel.open();
            socket.onopen = channel.socketOpened;
            socket.onmessage = channel.socketMessage;
            socket.onerror = channel.socketError;
            socket.onclose = channel.socketClosed;
        }
    },

    initChannels: function() {
        channel.initChannel($('meta[name="channel-token"]').attr('content'));
    },

    socketOpened: function() {},

    socketMessage: function(message) {
        var data = jQuery.parseJSON(message.data);
        if (data.event == "SERVER_STATUS") {
            channel.socketServerMessage(data);
        }
        else {
            channel.socketChatMessage(data);
        };
    },

    socketChatMessage: function(data) {
        if ($('.event_template').length) {
            channel.playSound(data.event);

            var eventDiv = $('.event_template')
                .first()
                .clone()
                .addClass(data.event + '_event')
                .addClass(data.username == channel.username ? 'you' : '');

            if (data.username) {
                eventDiv.find('.avatar').css('background-image', 'url(https://minotar.net/helm/' + data.username + '/20)');
                eventDiv.find('.name').text(data.username);
            }
            else {
                eventDiv.find('.avatar').css('background-image', 'url(https://minotar.net/helm/char/20)');
                eventDiv.find('.name').html('&lt;World&gt;');
            };
            eventDiv.find('.online .data').html(data.date + '&nbsp;&nbsp;' + data.time);

            var chatDiv = eventDiv.find('.chat');
            switch (data.event) {
                case 'chat':
                    chatDiv.text(data.chat);
                    break;
                case 'login':
                    chatDiv.text('Logged In');
                    channel.setPlayerPlaying(data.username);
                    break;
                case 'logout':
                    chatDiv.text('Logged Out');
                    channel.setPlayerNotPlaying(data.username);
                    break;
                case 'death':
                    chatDiv.text(data.death_message);
                    break;
                case 'achievement':
                    chatDiv.text(data.achievement_message);
                    break;
            }

            eventDiv.prependTo('#live_events').slideDown('fast');
        }
    },

    setPlayerPlaying: function(username) {
        if ($('.playing').length) {
            username_element_id = ".player#" + username;
            if ($(username_element_id).length) {
                $(username_element_id).find('.activity').addClass('on');
                $(username_element_id).prependTo('#all_players').slideDown('fast');
            }
            else {
                var userDiv = $('.playing_template').first().clone();
                userDiv.removeClass('playing_template');
                userDiv.attr('id', username);
                userDiv.find('.avatar').css('background-image', 'url(https://minotar.net/helm/' + username + '/40)');
                userDiv.find('.name').text(username);
                userDiv.prependTo('#all_players').slideDown('fast');
            }
        }
    },

    setPlayerNotPlaying: function(username) {
        if ($('.playing').length) {
            username_element_id = ".player#" + username;
            if ($(username_element_id).length) {
                $(username_element_id).find('.activity').removeClass('on');
            }
        }
    },

    socketServerMessage: function(data) {
        channel.setServerTimeWeather(data);
        channel.setServerStatusTime(data);
        channel.setServerOverloads(data);
        channel.setServerAddress(data);
        channel.setServerCommand(data);
        channel.setServerRestore(data);
        channel.setServerStatus(data);
        channel.showServerButtons(data);
        channel.setChatPlaceholder(data);
    },

    setServerTimeWeather: function(data) {
        day_element_id = "#" + data.server_id + " .server_day";
        time_element_id = "#" + data.server_id + " .server_time";
        weather_element_id = "#" + data.server_id + " .server_weather";
        if ($(day_element_id).length) {
            if (data.server_day != null) {
                $(day_element_id).text(data.server_day);
                $(time_element_id).text(data.server_time);
                if (data.is_raining) {
                    if (data.is_thundering) {
                        $(weather_element_id).text("Raining & Thundering");
                    }
                    else {
                        $(weather_element_id).text("Raining");
                    };
                }
                else {
                    $(weather_element_id).text("Clear");
                };
            }
            else {
                $(day_element_id).text("0");
                $(time_element_id).text("0");
                $(weather_element_id).text("Never Played");
            }
        }
    },

    setServerStatusTime: function(data) {
        element_id = "#" + data.server_id + " .server_last_ping";
        if ($(element_id).length && data.date) {
            $(element_id).html("(" + data.date + "&nbsp;&nbsp;" + data.time + ")");
        }
    },

    setServerOverloads: function(data) {
        element_id = "#" + data.server_id + " .server_num_overloads";
        if ($(element_id).length) {
            if (data.is_running && data.num_overloads) {
                $(element_id).html("5 Minute Lag Count:&nbsp;" + data.num_overloads).show();
            }
            else {
                $(element_id).hide()
            };
        }
    },

    setServerAddress: function(data) {
        element_id = "#" + data.server_id + " .server_address";
        if ($(element_id).length) {
            if (data.address) {
                $(element_id).html("<pre>"+data.address+"</pre>");
            }
            else if (data.is_stopped || data.is_unknown) {
                $(element_id).text("World Paused -- Press Play");
            }
            else if (data.is_queued_start) {
                $(element_id).text("World Starting...");
            }
            else if (data.is_queued_stop) {
                $(element_id).text("World Stopping...");
            }
            else {
                $(element_id).text("World Paused");
            };
        }
    },

    setServerCommand: function(data) {
        element_id = "#" + data.server_id + " .server_command";
        if ($(element_id).length) {
            if (data.is_running) {
                $(element_id).show();
            }
            else {
                $(element_id).hide();
            };
        }
    },

    setServerRestore: function(data) {
        element_id = "#" + data.server_id + " .server_restore";
        if ($(element_id).length) {
            if (data.is_gce) {
                if (data.is_stopped || data.is_unknown) {
                    $(element_id).show();
                }
                else {
                    $(element_id).hide();
                };
            }
        }
    },

    setServerStatus: function(data) {
        spinner_element_id = "#" + data.server_id + " .spinner";
        status = "unknown";
        status_text = "Existential Crisis";
        if (data.is_running) {
            status = "up";
            status_text = "Playing";
            $(spinner_element_id).hide();
        }
        if (data.is_stopped) {
            status = "down";
            status_text = "Defunct";
            $(spinner_element_id).hide();
        }
        completed = null;
        if (data.is_gce) {
            completed = data.completed
            if (data.is_stopped || data.is_unknown) {
                status = "down";
                status_text = "Paused";
                $(spinner_element_id).hide();
            }
            else if (data.is_queued_start) {
                status = "queued";
                status_text = "Prologue...";
                if (completed != null) {
                    status_text = "Remember...";
                }
                $(spinner_element_id).show();
            }
            else if (data.is_queued_restart) {
                status = "queued";
                status_text = "Resolution...";
                $(spinner_element_id).show();
            }
            else if (data.is_queued_stop) {
                status = "queued";
                status_text = "Epilogue...";
                if (completed != null) {
                    status_text = "Memorize...";
                }
                $(spinner_element_id).show();
            };
        }
        status_element_id = "#" + data.server_id + " .status";
        if ($(status_element_id).length) {
            $(status_element_id).removeClass("up down queued unknown").addClass(status);
        }
        status_text_element_id = "#" + data.server_id + " .server_status_text";
        if ($(status_text_element_id).length) {
            $(status_text_element_id).text(status_text)
        }
        completed_element_id = "#" + data.server_id + " .server_completed";
        if ($(completed_element_id).length) {
            if (completed != null) {
                $(completed_element_id).text(completed + "%");
            }
            else {
                $(completed_element_id).text("");
            };
        }
        shutdown_element_id = "#" + data.server_id + " .server_shutdown_in";
        if ($(shutdown_element_id).length) {
            if (data.idle_shutdown_in != null) {
                $(shutdown_element_id).html("<br/>" + data.idle_shutdown_in).show();
            }
            else {
                $(shutdown_element_id).hide();
            };
        }
    },

    showServerButtons: function(data) {
        eula_element_id = "#" + data.server_id + " .server_eula";
        play_element_id = "#" + data.server_id + " .server_play";
        restart_element_id = "#" + data.server_id + " .server_restart";
        save_element_id = "#" + data.server_id + " .server_save";
        pause_element_id = "#" + data.server_id + " .server_pause";
        if ($(eula_element_id).length && data.is_gce) {
            if (data.is_eula_agree) {
                $(eula_element_id).hide();
                if (data.is_stopped || data.is_unknown) {
                    $(play_element_id).show();
                    $(restart_element_id).hide();
                    $(save_element_id).hide();
                    $(pause_element_id).hide();
                }
                else if (data.admin) {
                    $(play_element_id).hide();
                    if (data.is_queued_start) {
                        $(restart_element_id).hide();
                        $(save_element_id).hide();
                        $(pause_element_id).show();
                    }
                    else if (data.is_queued_restart) {
                        $(restart_element_id).hide();
                        $(save_element_id).show();
                        $(pause_element_id).show();
                    }
                    else if (data.is_queued_stop) {
                        $(restart_element_id).hide();
                        $(save_element_id).hide();
                        $(pause_element_id).hide();
                    }
                    else {
                        $(restart_element_id).show();
                        $(save_element_id).show();
                        $(pause_element_id).show();
                    }
                }
                else {
                    $(play_element_id).hide();
                    $(restart_element_id).hide();
                    $(save_element_id).hide();
                    $(pause_element_id).hide();
                }
            }
            else {
                $(eula_element_id).show();
                $(play_element_id).hide();
                $(restart_element_id).hide();
                $(save_element_id).hide();
                $(pause_element_id).hide();
            }
        }
        else {
            $(eula_element_id).hide();
            $(play_element_id).hide();
            $(restart_element_id).hide();
            $(save_element_id).hide();
            $(pause_element_id).hide();
        };
    },

    setChatPlaceholder: function(data) {
        if ($("input[name='chat']").length) {
            if (data.is_running) {
                $("input[name='chat']").attr("placeholder", "Say something...");
            }
            else {
                $("input[name='chat']").attr("placeholder", "Say something... The server is not running but chats will be saved.");
            };
        }
    },

    socketError: function(error) {},

    socketClosed: function() {
        channel.playSound('brokenSocket');
        $('.live_updates_status').show();
    },

    initSound: function() {
        if ($.cookie('sound') == 'off') {
            channel.soundEnabled = false;
        }
        $('.sound_state').click(channel.toggleSoundState);
        channel.showSoundState();
    },

    sounds: {
        login: new buzz.sound('/sounds/door_open', { formats: [ 'ogg', 'mp3' ] }),
        logout: new buzz.sound('/sounds/chestclosed', { formats: [ 'ogg', 'mp3' ] }),
        chat: new buzz.sound('/sounds/bass', { formats: [ 'ogg', 'mp3' ] }),
        death: new buzz.sound('/sounds/hurt', { formats: [ 'ogg', 'mp3' ] }),
        achievement: new buzz.sound('/sounds/levelup', { formats: [ 'ogg', 'mp3' ] }),
        soundOn: new buzz.sound('/sounds/click', { formats: [ 'ogg', 'mp3' ] }),
        brokenSocket: new buzz.sound('/sounds/break', { formats: [ 'ogg', 'mp3' ] })
    },

    playSound: function(eventType) {
        if (channel.soundEnabled) {
            channel.sounds[eventType].play();
        }
    },

    toggleSoundState: function() {
        channel.soundEnabled = !channel.soundEnabled;
        if (channel.soundEnabled) {
            channel.playSound('soundOn');
        }
        $.cookie('sound', channel.soundEnabled ? 'on' : 'off', { expires: 3650, path: '/' });
        channel.showSoundState();
    },

    showSoundState: function() {
        $('.sound_state').text(
            channel.soundEnabled ? 'ON' : 'OFF'
        );
    }
};

var scroller = {
    init: function() {
        if ($('.infinite_scroll').length) {
            $(window).scroll(function() {
                scroller.didScroll = true;
            });

            setInterval(function() {
                if (scroller.didScroll) {
                    scroller.didScroll = false;
                    if ($(window).scrollTop() > $(document).height() - $(window).height() - 300) {
                        scroller.loadMore();
                    }
                }
            }, 250);

            $(window).scroll();
        }
    },

    loadMore: function() {
        var url = $('.infinite_scroll').data('url');
        if (url) {
            $('.infinite_scroll').data('url', '');
            $.getScript(url);
        }
    }
};

function enableFormSubmission(form) {
    form.on('submit', function(e) {
        e.preventDefault();
        submitForm(form);
    });
}

function submitForm(form) {
    var url = form.attr('action');
    $.ajax({
        type: 'POST',
        url: url,
        data: form.serialize(),
        success: function(result) {
            form.find('input[type="text"]').val('');
        }
    });
}

$(function() {
    channel.init();
    scroller.init();
    enableFormSubmission($('#chatform'));
});
