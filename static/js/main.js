// 寻味 · 收藏（localStorage）与少量交互
(function () {
  'use strict';

  var FAV_KEY = 'xunwei_favorites';

  function getFavs() {
    try {
      var saved = JSON.parse(localStorage.getItem(FAV_KEY));
      return Array.isArray(saved) ? Array.from(new Set(saved.map(String).filter(function (id) { return /^[1-9][0-9]{0,8}$/.test(id); }))).slice(0, 100) : [];
    } catch (e) {
      return [];
    }
  }

  function setFavs(list) {
    localStorage.setItem(FAV_KEY, JSON.stringify(list));
  }

  function updateFavCount() {
    var el = document.querySelector('[data-fav-count]');
    if (el) el.textContent = getFavs().length;
  }

  function initFavs() {
    if (window.XUNWEI && window.XUNWEI.loggedIn) {
      var local = getFavs();
      if (local.length) {
        fetch('/favorites/migrate', {method: 'POST',
          headers: {'Content-Type': 'application/json', 'X-CSRF-Token': window.XUNWEI.csrf},
          body: JSON.stringify({ids: local})
        }).then(function (r) { if (!r.ok || r.redirected) throw new Error('migration failed'); return r.json(); }).then(function (data) {
          localStorage.removeItem(FAV_KEY);
          var count = document.querySelector('[data-fav-count]');
          if (count) count.textContent = data.count;
          local.forEach(function (id) {
            document.querySelectorAll('[data-fav="' + id + '"]').forEach(function (b) { b.classList.add('is-active'); });
          });
          window.location.reload();
        }).catch(function () { showNotice('本地收藏暂未同步，稍后刷新可重试。'); });
      }
      return;
    }
    var favs = getFavs();
    document.querySelectorAll('[data-fav]').forEach(function (btn) {
      btn.classList.toggle('is-active', favs.indexOf(btn.getAttribute('data-fav')) !== -1);
    });
    updateFavCount();
  }

  function showNotice(message) {
    var notice = document.querySelector('[data-notice]');
    if (!notice) {
      notice = document.createElement('p');
      notice.dataset.notice = 'true';
      notice.className = 'flash flash--error';
      notice.setAttribute('role', 'status');
      document.querySelector('main').prepend(notice);
    }
    notice.textContent = message;
  }

  function toggleServer(id) {
    var body = new URLSearchParams({csrf_token: window.XUNWEI.csrf});
    return fetch('/favorite/' + id, {method: 'POST', body: body,
      headers: {'X-Requested-With': 'XMLHttpRequest'}}).then(function (r) {
      if (!r.ok) throw new Error('request failed');
      return r.json();
    }).then(function (data) {
      document.querySelectorAll('[data-fav="' + id + '"]').forEach(function (b) {
        b.classList.toggle('is-active', data.active);
      });
      var count = document.querySelector('[data-fav-count]');
      if (count) count.textContent = data.count;
      return data;
    });
  }

  // 事件委托：点击收藏按钮
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-fav]');
    if (!btn) return;
    var id = btn.getAttribute('data-fav');
    if (window.XUNWEI && window.XUNWEI.loggedIn) {
      btn.disabled = true;
      toggleServer(id).then(function () {
        var current = new URL(window.location.href);
        if (current.searchParams.get('favorites') === '1' ||
            (current.pathname === '/profile' && (current.searchParams.get('tab') || 'favorites') === 'favorites')) window.location.reload();
      }).catch(function () { showNotice('收藏保存失败，请刷新或重新登录后重试。'); })
        .finally(function () { btn.disabled = false; });
      return;
    }
    var favs = getFavs();
    var i = favs.indexOf(id);
    if (i === -1) {
      favs.push(id);
    } else {
      favs.splice(i, 1);
    }
    try { setFavs(favs); } catch (error) { showNotice('浏览器无法保存本地收藏，请登录后使用账号收藏。'); return; }
    btn.classList.toggle('is-active', i === -1);
    updateFavCount();
  });

  // 只看收藏筛选
  var favFilter = document.getElementById('fav-filter');
  if (favFilter) {
    favFilter.addEventListener('click', function () {
      var url = new URL(window.location.href);
      var on = url.searchParams.get('favorites') !== '1';
      url.searchParams.set('favorites', on ? '1' : '0');
      url.searchParams.delete('page');
      if (on && !window.XUNWEI.loggedIn) url.searchParams.set('ids', getFavs().join(','));
      else url.searchParams.delete('ids');
      window.location.assign(url.toString());
    });
  }

  // 选择综合评分时，自动同步分项评分
  var form = document.getElementById('review-form');
  if (form) {
    var radios = form.querySelectorAll('input[name="rating"]');
    radios.forEach(function (radio) {
      radio.addEventListener('change', function () {
        ['taste_score', 'environment_score', 'service_score'].forEach(function (name) {
          var sel = form.querySelector('select[name="' + name + '"]');
          if (sel) sel.value = radio.value;
        });
      });
    });
  }

  initFavs();
})();
