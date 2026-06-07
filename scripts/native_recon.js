/*
 * native_recon.js — native loading + JNI registration tracer
 * frida -U -f <pkg> -l native_recon.js --no-pause
 *
 * Prints: which .so load (and when), JNI_OnLoad calls, and the full RegisterNatives
 * table (JavaClass.method(sig) -> native fnptr @ module+offset). This is how you locate
 * a sign/encrypt function inside a .so that only exports JNI_OnLoad.
 *
 * Optional: set TARGET_LIBS to focus the RegisterNatives dump on specific libs.
 */
'use strict';
var TARGET_LIBS = [];            // e.g. ['libNetHTProtect.so'] — empty = all
function L(m){ console.log('[recon] ' + m); }
function want(name){ return TARGET_LIBS.length === 0 || TARGET_LIBS.indexOf(name) !== -1; }

// 1) Trace dlopen so we catch protected libs that load late
['android_dlopen_ext', 'dlopen'].forEach(function (sym) {
  var p = Module.findExportByName(null, sym);
  if (!p) return;
  Interceptor.attach(p, {
    onEnter: function (a) { try { this.path = a[0].readCString(); } catch (e) { this.path = '?'; } },
    onLeave: function () { if (this.path && /\.so/.test(this.path)) L('dlopen ' + this.path); }
  });
});

// 2) Hook RegisterNatives via libart symbol
function hookRegisterNatives() {
  var libart = Process.findModuleByName('libart.so');
  if (!libart) { L('libart not found yet'); return false; }
  var pRN = null;
  libart.enumerateSymbols().forEach(function (s) {
    if (s.name.indexOf('RegisterNatives') !== -1 && s.name.indexOf('CheckJNI') === -1 && !pRN) pRN = s.address;
  });
  if (!pRN) { L('RegisterNatives symbol not found'); return false; }

  var SZ = Process.pointerSize * 3;
  Interceptor.attach(pRN, {
    onEnter: function (args) {
      var jclass = args[1], methods = args[2], count = args[3].toInt32();
      var cls = '?';
      try { cls = Java.vm.tryGetEnv().getClassName(jclass); } catch (e) {}
      L('RegisterNatives ' + cls + ' (' + count + ' methods)');
      for (var i = 0; i < count; i++) {
        var nm = '?', sig = '?', fn = ptr(0), mod = '?';
        try {
          nm  = Memory.readCString(Memory.readPointer(methods.add(i * SZ)));
          sig = Memory.readCString(Memory.readPointer(methods.add(i * SZ + Process.pointerSize)));
          fn  = Memory.readPointer(methods.add(i * SZ + Process.pointerSize * 2));
          var d = Process.findModuleByAddress(fn);
          mod = d ? (d.name + '+0x' + fn.sub(d.base).toString(16)) : fn.toString();
        } catch (e) {}
        if (mod === '?' || want(mod.split('+')[0])) L('   ' + cls + '.' + nm + sig + '  ->  ' + mod);
      }
    }
  });
  L('RegisterNatives hooked'); return true;
}

// 3) JNI_OnLoad per module (init order, where natives get registered)
['android_dlopen_ext', 'dlopen'].forEach(function (sym) {
  var p = Module.findExportByName(null, sym); if (!p) return;
  Interceptor.attach(p, { onLeave: function () {
    Process.enumerateModules().forEach(function (m) {
      if (!m.__seen && /\.so$/.test(m.name)) {
        m.__seen = true;
        var jol = Module.findExportByName(m.name, 'JNI_OnLoad');
        if (jol) L('JNI_OnLoad present in ' + m.name + ' @ ' + jol);
      }
    });
  }});
});

if (!hookRegisterNatives()) {
  // retry once libart is up
  var iv = setInterval(function () { if (hookRegisterNatives()) clearInterval(iv); }, 50);
  setTimeout(function () { clearInterval(iv); }, 5000);
}
