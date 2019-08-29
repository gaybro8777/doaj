// anywhere a form is instantiated on the UI from a record in the backend, 
// poll that record and monitor the form changes to warn the user of clashes
// can provide custom function to highlight, notify, and warn, or set them to false if no action desired for them
// the defaults simply set a red outline on contested elements, and show a warning message at the bottom of the form
// a submit function can also be provided if custom submit functionality is required.
// Also a "partial" function or string is allowed, which simplifies the retrieved record if necessary.
// For example if the relevant part of the GET response JSON is in a key called "data", set the value of "partial" to "data"
// Dot notation works for extraction in this way. If a more complex method is required for getting at the relevant data, 
// then "partial" can be a function which will be passed the response JSON, and can augment and return it as necessary.
// See below for how these are tied to the UI and what values they are passed, so you can customise them if desired
// see also other options below

// form elements on the UI should be inside a form, and that form should have a submit trigger
// each element should have an "id" or other attribute (which can be customised in options.key)
// that attribute should have the dot notation of the key that the element value is for
// values in lists can be reached using numbers, e.g. identifiers.0.doi is the "doi" key of the first object in the "identifiers" list
// the UI should handle how to add/remove sets of form elements to allow editing of complex objects, and as long as it 
// follows this naming convention, they will be tracked and updated

// NOTE: this poller does NOT do the save. That has to be handled by the form or other js on the UI, reading the form
// It would be possible to add save to this, but depends a lot on what the backend can accept (partial/total updates, etc), 
// so not worth generalising here.

var poller = function(options) {
  if (options === undefined) options = {};
  var url = options.url === undefined ? window.location.href : options.url; // the url to GET the latest state from
  var form = options.form === undefined ? 'body' : options.form; // ideally should be the #id of the form to poll
  var populate = options.populate; // if true the form fields will be populated from the record at startup
  // if no record provided, it will be retrieved from the URL at startup 
  var record = options.record === true || options.record === undefined ? {} : options.record;
  var _part = typeof options.partial === 'string' ? options.partial : undefined;
  var partial = function(record) {
    // 
    var res = undefined;
    try { res = _part ? _dot(record,_part) : record; } catch(err) {}
    return res ? res : record;
  }
  if (typeof options.partial === 'function') partial = options.partial;
  record = partial(record);
  var key = options.key === undefined ? 'id' : options.key; // element attribute name where can find the identifying string that points to the element value within the overall record object (dot notation if nested)
  var interval = options.interval === undefined ? 5000 : options.interval; // how often to poll, defaults to 5s
  var highlight = options.highlight;
  if (highlight === undefined) {
    $('body').append('<style>.poller_highlight { outline: 1px solid red !important;}</style>');
    highlight = function(elem,clear,val) { // highlight clashing elements when possible
      // if highlighting can't be reliably done due to how data is stored in the record or displayed on the form, then set highlight to false
      // a general notification will still be shown any time there are changes to the same elements
      if (clear) {
        if (elem.attr('placeholder')) elem.attr('placeholder',elem.attr('_original_placeholder')).removeAttr('_original_placeholder');
        elem.removeClass('poller_highlight');
      } else {
        if (val) elem.attr('_original_placeholder',elem.attr('placeholder')).attr('placeholder','The remote ' + elem.attr(key) + ' value is ' + val);
        elem.addClass('poller_highlight');
      }
    }
  }
  var notify = options.notify;
  if (notify === undefined) {
    notify = function(different) { // notify the user that the remote has changed and local has changed, so there could be a clash
      if (different) {
        if (!$('.poller_notify',form).length) {
          // add a notification just before the form submit button if present, or at the end of the form element (whatever element that may be)
          var note = '<div class="poller_notify alert alert-warning"><p>There are clashing changes since you began editing.</p></div>';
          $('input[type="submit"]',form).length ? $('input[type="submit"]',form).after(note) : $(form).children().last().after(note);
        }
      } else {
        $('.poller_notify',form).remove();
      }
    }
  }
  var warn = options.warn;
  var submit = options.submit;
  if (warn === undefined) {
    warn = function(e) { // warn the user if they try to save when potential clashes are present
      var s = confirm('There are local changes that will clash with remote changes. Are you sure you want to save without fixing?');
      if (!s) {
        e.preventDefault(); // stop the form submission if user cancels
      } else {
        try {
          submit(e); // if a function is provided for submit, it is called here, and passed the event context, so can be prevented or prefixed, etc
        } catch(err) {}
      }
    }
  }
  var evaluate = options.evaluate;
  if (evaluate === undefined) {
    evaluate = function(elem) {
      // customise how to read values out of form fields, if necessary, where elem is $(this) so could customise by key too
      if (elem.is(':checkbox')) {
        return elem.is(':checked');
      } else if (elem.is(':radio')) {
        return $("input[" + key + "='" + $(this).attr(key) + "']:checked",form).val();
      } else {
        return elem.val();
      }
    }
  }
  var auth = options.auth === undefined ? {} : options.auth; // see below how to provide auth in various ways in an auth object
  var test = options.test; // if true, any top level text values in the record will have _test appended, which will cause subsequent edits to trigger the highlights, warnings, etc
  
  var _init = {}; // store the initial values of all form elements
  var _different = {}; // track differences as they occur

  // main poll function, which is called at set intervals
  var poll = function() {
    var opts = {
      url: url,
      type: 'GET',
      success: function(latest) {
        latest = partial(latest);
        if (JSON.stringify(record) === '{}') record = latest; // first time, set the record if it was not passed at init
        if (test && !populate) {
          for ( var k in latest ) {
            if (typeof latest[k] === 'string') latest[k] += '_test';
          }
        }
        // if remote record is different from local, there has been a remote change, so check for local changes
        // if it is not different, local changes have nothing to clash against, so nothing needs to be done
        if (populate || JSON.stringify(record).split('').sort().join('') !== JSON.stringify(latest).split('').sort().join('')) {
          $('input,textarea,select',form).each(function() {
            // trying to only run each on the ones with the key did not work, so check here
            if ($(this).attr(key)) {
              if (_init[$(this).attr(key)] === undefined) {
                if (populate) $(this).val(_dot(record, $(this).attr(key)));
                _init[$(this).attr(key)] = evaluate($(this));
              }
              var currentval = evaluate($(this));
              var latestval = _dot(latest, $(this).attr(key));
              if (typeof latestval === 'object') { // simplify further to try comparing to local current values in form
                latestval = JSON.stringify(latestval);
                if (latestval.indexOf('[') === 0) latestval = latestval.replace(/\[/g,'').replace(/\]/g,'');
              }
              if (_init[$(this).attr(key)] !== currentval && _init[$(this).attr(key)] !== latestval && typeof latestval === 'string' && currentval.replace(/ /g,'').split('').sort().join('') !== latestval.replace(/ /g,'').split('').sort().join('')) {
                // if there is a change and it can't be matched to the same remote change, highlight the possible clash
                _different[$(this).attr(key)] = currentval;
                if (typeof highlight === 'function') highlight($(this),typeof _different[$(this).attr(key)] === undefined,latestval);
              } else if (typeof _different[$(this).attr(key)] !== undefined) {
                delete _different[$(this).attr(key)];
                highlight($(this),true);
              }
            }
          });
          populate = false;
        }
        if (typeof notify === 'function') notify(JSON.stringify(_different) !== '{}');
      }
    };
    if (auth.username && auth.password) opts.headers = { "Authorization": "Basic " + btoa(auth.username + ":" + auth.password) };
    if (auth.apikey) opts.url += opts.url.indexOf('?') === -1 ? '?apikey=' + auth.apikey : '&apikey=' + auth.apikey;
    if (auth['x-apikey']) opts.beforeSend = function (request) { request.setRequestHeader("x-apikey", auth['x-apikey']); };
    if (auth.header) auth.headers = auth.header;
    if (auth.param) auth.params = auth.param;
    if (auth.value) auth.values = auth.value;
    if (typeof auth.headers === 'string') auth.headers = [auth.headers];
    if (typeof auth.params === 'string') auth.params = [auth.params];
    if (typeof auth.values === 'string') auth.values = [auth.values];
    if ((auth.headers || auth.params) && auth.values) {
      if (auth.headers) {
        opts.beforeSend = function (request) { 
          for ( var v in auth.headers ) {
            request.setRequestHeader(auth.headers[v], auth.values[v]); 
          }
        };
      } else {
        for ( var v in auth.params ) {
          opts.url += (opts.url.indexOf('?') === -1 ? '?' : '&') + auth.params[v] + '=' + auth.values[v];
        }
      }
    }
    $.ajax(opts);
  }
  if (populate) poll(); // poll immediately if populate is true
  var _pollid = setInterval(poll, interval);
  
  if (form !== 'body') {
    $(form).on('submit',function(e) {
      if (JSON.stringify(_different) !== '{}' && typeof warn === 'function') warn(e);
    });
  }
  
  return _pollid; // polling can be cancelled by the main js using the poll ID later, if necessary
}

// the usual handy function for getting/setting values in an object by dot notation
var _dot = function(obj, key, value, del) {
  if (typeof key === 'string') {
    return _dot(obj, key.split('.'), value, del);
  } else if (key.length === 1 && (value !== undefined || del !== undefined)) {
    if (del === true || value === '$DELETE') {
      if (obj instanceof Array) {
        obj.splice(key[0], 1);
      } else {
        delete obj[key[0]];
      }
      return true
    } else {
      obj[key[0]] = value;
      return true
    }
  } else if (key.length === 0) {
    return obj;
  } else {
    if (obj[key[0]] === undefined) {
      if (value !== undefined) {
        obj[key[0]] = isNaN(parseInt(key[0])) ? {} : [];
        return _dot(obj[key[0]], key.slice(1), value, del);
      } else {
        return undefined;
      }
    } else {
      return _dot(obj[key[0]], key.slice(1), value, del);
    }
  }
}
