var chats = {
    username: null,
    soundEnabled: true,

    init: function() {
        chats.username = $('meta[name="username"]').attr('content');
        chats.initChannel();
        chats.initSound();
    },

    initChannel: function() {
        var token = $('meta[name="channel-token"]').attr('content');
        var channel = new goog.appengine.Channel(token);
        var socket = channel.open();
        socket.onopen = chats.socketOpened;
        socket.onmessage = chats.socketMessage;
        socket.onerror = chats.socketError;
        socket.onclose = chats.socketClosed;
    },

    socketOpened: function() {},

    socketMessage: function(message) {
        var data = jQuery.parseJSON(message.data);
        if (data.event == "SERVER_STATUS") {
            chats.socketServerMessage(data);
        }
        else {
            chats.socketChatMessage(data);
        }
    },

    socketChatMessage: function(data) {
        if ($('.event_template').length) {
            chats.playSound(data.event);

            var eventDiv = $('.event_template')
                .first()
                .clone()
                .addClass(data.event + '_event')
                .addClass(data.username == chats.username ? 'you' : '');

            eventDiv.find('.avatar').css('background-image', 'url(https://minotar.net/helm/' + data.username + '/20)');
            eventDiv.find('.name').text(data.username);
            eventDiv.find('.online .data').html(data.date + '&nbsp;&nbsp;' + data.time);

            var chatDiv = eventDiv.find('.chat');
            switch (data.event) {
                case 'chat':
                    chatDiv.text(data.chat);
                    break;
                case 'login':
                    chatDiv.text('Logged in');
                    break;
                case 'logout':
                    chatDiv.text('Logged out');
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

    socketServerMessage: function(data) {
        chats.setServerTimeWeather(data);
        chats.setServerStatusTime(data);
        chats.setServerAddress(data);
        chats.setServerCommand(data);
        chats.setServerRestore(data);
        chats.setServerStatus(data);
        chats.showServerButtons(data);
    },

    setServerTimeWeather: function(data) {
        if ($('.server_day').length) {
            $('.server_day').text(data.server_day);
            $('.server_time').text(data.server_time);
            if (data.is_raining) {
                if (data.is_thundering) {
                    $('.server_weather').text("Raining & Thundering");
                }
                else {
                    $('.server_weather').text("Raining");
                };
            }
            else {
                $('.server_weather').text("Clear");
            };
        }
    },

    setServerStatusTime: function(data) {
        if ($('.server_last_ping').length && data.date) {
            $('.server_last_ping').html("(" + data.date + "&nbsp;&nbsp;" + data.time + ")");
        }
    },

    setServerAddress: function(data) {
        if ($('.server_address').length) {
            if (data.address) {
                $('.server_address').html("<pre>"+data.address+"</pre>");
            }
            else if (data.is_stopped || data.is_unknown) {
                $('.server_address').text("World Paused -- Press Play");
            }
            else if (data.is_queued_start) {
                $('.server_address').text("World Starting...");
            }
            else if (data.is_queued_stop) {
                $('.server_address').text("World Stopping...");
            }
            else {
                $('.server_address').text("World Paused");
            };
        }
    },

    setServerCommand: function(data) {
        if ($('.server_command').length) {
            if (data.is_running) {
                $('.server_command').show();
            }
            else {
                $('.server_command').hide();
            };
        }
    },

    setServerRestore: function(data) {
        if ($('.server_restore').length) {
            if (data.is_gce) {
                if (data.is_stopped || data.is_unknown) {
                    $('.server_restore').show();
                }
                else {
                    $('.server_restore').hide();
                };
            }
        }
    },

    setServerStatus: function(data) {
        status = "unknown";
        status_text = "Existential Crisis";
        if (data.is_running) {
            status = "up";
            status_text = "Playing";
            $('.spinner').hide();
        }
        if (data.is_stopped) {
            status = "down";
            status_text = "Defunct";
            $('.spinner').hide();
        }
        completed = null;
        if (data.is_gce) {
            completed = data.completed
            if (data.is_stopped || data.is_unknown) {
                status = "down";
                status_text = "Paused";
                $('.spinner').hide();
            }
            else if (data.is_queued_start) {
                status = "queued";
                status_text = "Prologue...";
                if (completed != null) {
                    status_text = "Remember...";
                }
                $('.spinner').show();
            }
            else if (data.is_queued_restart) {
                status = "queued";
                status_text = "Resolution...";
                $('.spinner').show();
            }
            else if (data.is_queued_stop) {
                status = "queued";
                status_text = "Epilogue...";
                if (completed != null) {
                    status_text = "Memorize...";
                }
                $('.spinner').show();
            };
        }
        if ($('.status').length) {
            $('.status').removeClass("up down queued unknown");
            $('.status').addClass(status);
        }
        if ($('.server_status_text').length) {
            $('.server_status_text').text(status_text)
        }
        if ($('.server_completed').length) {
            if (completed != null) {
                $('.server_completed').text(completed + "%");
            }
            else {
                $('.server_completed').text("");
            };
        }
        if ($('.server_shutdown_in').length) {
            if (data.idle_shutdown_in != null) {
                $('.server_shutdown_in').html("<br/>" + data.idle_shutdown_in);
                $('.server_shutdown_in').show();
            }
            else {
                $('.server_shutdown_in').hide();
            };
        }
    },

    showServerButtons: function(data) {
        if ($('.server_eula').length && data.is_gce) {
            if (data.is_eula_agree) {
                $('.server_eula').hide();
                if (data.is_stopped || data.is_unknown) {
                    $('.server_play').show();
                    $('.server_restart').hide();
                    $('.server_save').hide();
                    $('.server_pause').hide();
                }
                else if (data.admin) {
                    $('.server_play').hide();
                    if (data.is_queued_start) {
                        $('.server_restart').hide();
                        $('.server_save').hide();
                        $('.server_pause').show();
                    }
                    else if (data.is_queued_restart) {
                        $('.server_restart').hide();
                        $('.server_save').show();
                        $('.server_pause').show();
                    }
                    else if (data.is_queued_stop) {
                        $('.server_restart').hide();
                        $('.server_save').hide();
                        $('.server_pause').hide();
                    }
                    else {
                        $('.server_restart').show();
                        $('.server_save').show();
                        $('.server_pause').show();
                    }
                }
                else {
                    $('.server_play').hide();
                    $('.server_restart').hide();
                    $('.server_save').hide();
                    $('.server_pause').hide();
                }
            }
            else {
                $('.server_eula').show();
                $('.server_play').hide();
                $('.server_restart').hide();
                $('.server_save').hide();
                $('.server_pause').hide();
            }
        }
        else {
            $('.server_eula').hide();
            $('.server_play').hide();
            $('.server_restart').hide();
            $('.server_save').hide();
            $('.server_pause').hide();
        };
    },

    socketError: function(error) {},

    socketClosed: function() {
        chats.playSound('brokenSocket');
        $('.live_updates_status').show();
    },

    initSound: function() {
        if ($.cookie('sound') == 'off') {
            chats.soundEnabled = false;
        }
        $('.sound_state').click(chats.toggleSoundState);
        chats.showSoundState();
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
        if (chats.soundEnabled) {
            chats.sounds[eventType].play();
        }
    },

    toggleSoundState: function() {
        chats.soundEnabled = !chats.soundEnabled;
        if (chats.soundEnabled) {
            chats.playSound('soundOn');
        }
        $.cookie('sound', chats.soundEnabled ? 'on' : 'off', { expires: 3650, path: '/' });
        chats.showSoundState();
    },

    showSoundState: function() {
        $('.sound_state').text(
            chats.soundEnabled ? 'ON' : 'OFF'
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
    chats.init();
    scroller.init();
    enableFormSubmission($('#chatform'));
});
