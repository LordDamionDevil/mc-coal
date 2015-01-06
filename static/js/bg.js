function resize_bg() {
    bgw = $('.bg').width();
    offsetw = bgw - $(window).width();
    $('.bg').css("left", offsetw/2*-1);
}

$(function() {
    if ($('.bg').length) {
        resize_bg();
        $(window).resize(function () {
            resize_bg();
        });
    }
});
