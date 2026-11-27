// DisplayPad.app (built by launcher/build.sh, from install.sh): the configurator in a window of
// its own, without the browser around it, and the floating pad that a shortcut brings up at the
// mouse.
//
// It talks to the DisplayPad service (displaypad_mac, a LaunchAgent) on 127.0.0.1:
//   - GET /api/popup/wait stays open until the floating pad must show, or its settings change.
//     The service watches the mouse buttons; a keyboard shortcut is registered here, as a system
//     hotkey (that needs no permission).
//   - /pad is the floating pad's page and / the configurator; both take the key in .token.
// Started with --background (by the service: at login, after a crash) it waits with no window
// and no Dock icon. Opened from Finder, Spotlight or the pad's Configure key, it shows the
// configurator. With the floating pad off, it quits when the window closes.
// When the service finds a newer version on GitHub, it says so once in a notification.

import Carbon.HIToolbox
import Cocoa
import UserNotifications
import WebKit

// MARK: - options and text

struct Options {
    var port = 8765
    var dir = NSHomeDirectory() + "/Library/Application Support/DisplayPadMac"
    var background = false
    var popup = false

    init(_ args: [String]) {
        var it = args.dropFirst().makeIterator()
        while let a = it.next() {
            switch a {
            case "--port": if let v = it.next(), let n = Int(v) { port = n }
            case "--dir": if let v = it.next(), !v.isEmpty { dir = v }
            case "--background": background = true
            case "--popup": popup = true; background = true
            default: break  // -psn_… from Finder on older systems, and anything else
            }
        }
    }
}

let opts = Options(CommandLine.arguments)
let appVersion = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "dev"
let repoURL = "https://github.com/jgptrd/displaypad-mac"

/// "en" or "es": the configurator's language (config.json), and then what the service says.
var language: String = {
    guard let data = FileManager.default.contents(atPath: opts.dir + "/config.json"),
          let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
          let lang = obj["language"] as? String else { return "en" }
    return lang
}()

func tr(_ en: String, _ es: String) -> String { language == "es" ? es : en }

/// DISPLAYPAD_DEBUG=1: what the web views do, on stderr (and the pages can be inspected in Safari).
let debugging = ProcessInfo.processInfo.environment["DISPLAYPAD_DEBUG"] == "1"
func note(_ s: @autoclosure () -> String) { if debugging { FileHandle.standardError.write((s() + "\n").data(using: .utf8)!) } }

// MARK: - the service

enum Service {
    static var base: String { "http://127.0.0.1:\(opts.port)" }

    static func token() -> String? {
        guard let s = try? String(contentsOfFile: opts.dir + "/.token", encoding: .utf8) else { return nil }
        let tok = s.trimmingCharacters(in: .whitespacesAndNewlines)
        return tok.isEmpty ? nil : tok
    }

    static func pageURL(_ path: String) -> URL? {
        guard let tok = token() else { return nil }
        return URL(string: "\(base)\(path)#t=\(tok)")
    }

    static let session: URLSession = {
        let c = URLSessionConfiguration.ephemeral
        c.connectionProxyDictionary = [:]  // straight to 127.0.0.1, whatever proxy is set
        c.timeoutIntervalForRequest = 60
        c.requestCachePolicy = .reloadIgnoringLocalCacheData
        return URLSession(configuration: c)
    }()

    /// done(HTTP status, JSON object) on the main thread; status 0: no answer.
    static func call(_ path: String, method: String = "GET", body: [String: Any]? = nil, timeout: TimeInterval = 10,
                     done: @escaping (Int, [String: Any]?) -> Void) {
        guard let url = URL(string: base + path) else { return }
        var r = URLRequest(url: url, timeoutInterval: timeout)
        r.httpMethod = method
        if let tok = token() { r.setValue(tok, forHTTPHeaderField: "X-Token") }
        if let body = body {
            r.httpBody = try? JSONSerialization.data(withJSONObject: body)
            r.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        session.dataTask(with: r) { data, resp, _ in
            let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
            let obj = data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
            DispatchQueue.main.async { done(code, obj) }
        }.resume()
    }

    static func isUp(_ done: @escaping (Bool) -> Void) {
        call("/", timeout: 1.5) { code, _ in done(code != 0) }
    }

    /// Starts the service if it isn't answering and waits up to 10 seconds for it.
    static func ensureUp(_ done: @escaping (Bool) -> Void) {
        isUp { up in
            if up { return done(true) }
            let p = Process()
            p.executableURL = URL(fileURLWithPath: "/bin/launchctl")
            p.arguments = ["kickstart", "gui/\(getuid())/com.displaypadmac.agent"]
            p.standardOutput = FileHandle.nullDevice
            p.standardError = FileHandle.nullDevice
            try? p.run()
            var tries = 0
            func again() {
                tries += 1
                isUp { up in
                    if up || tries >= 20 { done(up) } else { DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { again() } }
                }
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { again() }
        }
    }
}

/// Script messages without the web view keeping its owner alive.
final class WeakHandler: NSObject, WKScriptMessageHandler {
    weak var target: WKScriptMessageHandler?
    init(_ target: WKScriptMessageHandler) { self.target = target }
    func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) {
        target?.userContentController(c, didReceive: m)
    }
}

// MARK: - keyboard shortcut

/// The floating pad's keyboard shortcut, as a system hotkey: works in every app, with no permission.
final class Hotkey {
    private var ref: EventHotKeyRef?
    private var current: (UInt32, UInt32)?
    private(set) var state = "off"  // off | ok | taken | error<status>
    static var onPress: (() -> Void)?
    private static var installed = false

    func set(code: UInt32?, mods: UInt32) {
        if let code = code, let cur = current, cur == (code, mods), ref != nil { return }
        if let r = ref { UnregisterEventHotKey(r) }
        ref = nil
        current = nil
        guard let code = code else { state = "off"; return }
        if !Hotkey.installed {
            var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
            InstallEventHandler(GetApplicationEventTarget(), { _, _, _ in
                DispatchQueue.main.async { Hotkey.onPress?() }
                return noErr
            }, 1, &spec, nil, nil)
            Hotkey.installed = true
        }
        let id = EventHotKeyID(signature: OSType(0x4450_6164), id: 1)  // "DPad"
        let status = RegisterEventHotKey(code, mods, id, GetApplicationEventTarget(), 0, &ref)
        if status == noErr {
            state = "ok"
            current = (code, mods)
        } else {
            state = status == OSStatus(eventHotKeyExistsErr) ? "taken" : "error\(status)"
            ref = nil
        }
    }
}

// MARK: - floating pad

final class PopupPanel: NSPanel {
    override var canBecomeKey: Bool { true }  // for Esc and the number keys
    override var canBecomeMain: Bool { false }
}

/// A rounded shape for the blurred background (and so for the panel's shadow).
func roundedMask(radius r: CGFloat) -> NSImage {
    let img = NSImage(size: NSSize(width: r * 2 + 1, height: r * 2 + 1), flipped: false) { rect in
        NSColor.black.setFill()
        NSBezierPath(roundedRect: rect, xRadius: r, yRadius: r).fill()
        return true
    }
    img.capInsets = NSEdgeInsets(top: r, left: r, bottom: r, right: r)
    img.resizingMode = .stretch
    return img
}

/// The pad's keys in a panel at the mouse. The panel never makes this app the active one, so the
/// app in front keeps its place: a key's shortcut or typed text goes there once the panel is away.
final class FloatingPad: NSObject, NSWindowDelegate, WKNavigationDelegate, WKScriptMessageHandler {
    let panel: PopupPanel
    let web: WKWebView
    var onConfigure: (() -> Void)?
    private var ready = false
    private var showWhenReady = false
    private var opening = false
    private var monitor: Any?
    private var hiddenAt = Date.distantPast

    override init() {
        panel = PopupPanel(contentRect: NSRect(x: 0, y: 0, width: 526, height: 272),
                           styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
        let conf = WKWebViewConfiguration()
        conf.applicationNameForUserAgent = "DisplayPadApp/\(appVersion)"
        web = WKWebView(frame: .zero, configuration: conf)
        super.init()
        if debugging, #available(macOS 13.3, *) { web.isInspectable = true }
        web.configuration.userContentController.add(WeakHandler(self), name: "dp")
        panel.isFloatingPanel = true
        panel.level = .popUpMenu
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .transient, .ignoresCycle]
        panel.hidesOnDeactivate = false
        panel.becomesKeyOnlyIfNeeded = false
        panel.worksWhenModal = true
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = true
        panel.isReleasedWhenClosed = false
        panel.animationBehavior = .none
        panel.appearance = NSAppearance(named: .darkAqua)
        panel.delegate = self
        let fx = NSVisualEffectView(frame: NSRect(x: 0, y: 0, width: 526, height: 272))
        fx.material = .hudWindow
        fx.blendingMode = .behindWindow
        fx.state = .active
        fx.maskImage = roundedMask(radius: 18)
        panel.contentView = fx
        web.frame = fx.bounds
        web.autoresizingMask = [.width, .height]
        web.setValue(false, forKey: "drawsBackground")
        web.navigationDelegate = self
        fx.addSubview(web)
    }

    func load() {
        ready = false
        guard let url = Service.pageURL("/pad") else { return retry() }
        web.load(URLRequest(url: url))
    }

    private func retry() {
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in
            if self?.ready == false { self?.load() }
        }
    }

    func toggle() {
        if panel.isVisible { return hide() }
        if Date().timeIntervalSince(hiddenAt) < 0.35 { return }  // the same click put it away
        show()
    }

    func show(at point: NSPoint? = nil) {
        guard ready else { showWhenReady = true; return }
        if opening || panel.isVisible { return }
        opening = true
        let mouse = point ?? NSEvent.mouseLocation
        // the page draws the page the pad shows, then says how big it is
        web.callAsyncJavaScript("return await dpShow()", arguments: [:], in: nil, in: .page) { [weak self] result in
            guard let self = self else { return }
            self.opening = false
            var size = NSSize(width: 526, height: 272)
            if case .success(let v) = result, let d = v as? [String: Any],
               let w = (d["w"] as? NSNumber)?.doubleValue, let h = (d["h"] as? NSNumber)?.doubleValue, w > 100, h > 100 {
                size = NSSize(width: w, height: h)
            }
            self.present(at: mouse, size: size)
        }
    }

    private func present(at p: NSPoint, size: NSSize) {
        let screen = NSScreen.screens.first { NSMouseInRect(p, $0.frame, false) } ?? NSScreen.main ?? NSScreen.screens[0]
        let area = screen.visibleFrame.insetBy(dx: 6, dy: 6)
        var o = NSPoint(x: (p.x - size.width / 2).rounded(), y: (p.y - size.height / 2).rounded())
        o.x = max(area.minX, min(o.x, area.maxX - size.width))
        o.y = max(area.minY, min(o.y, area.maxY - size.height))
        panel.setFrame(NSRect(origin: o, size: size), display: true)
        panel.alphaValue = 0
        panel.makeKeyAndOrderFront(nil)
        panel.makeFirstResponder(web)
        panel.invalidateShadow()
        NSAnimationContext.runAnimationGroup { ctx in
            ctx.duration = 0.1
            panel.animator().alphaValue = 1
        }
        if monitor == nil {  // a click anywhere else puts it away
            monitor = NSEvent.addGlobalMonitorForEvents(matching: [.leftMouseDown, .rightMouseDown, .otherMouseDown]) { [weak self] _ in
                self?.hide()
            }
        }
    }

    func hide() {
        if let m = monitor {
            NSEvent.removeMonitor(m)
            monitor = nil
        }
        showWhenReady = false
        guard panel.isVisible else { return }
        hiddenAt = Date()
        panel.orderOut(nil)
        web.evaluateJavaScript("window.dpHide && dpHide()", completionHandler: nil)
    }

    func windowDidResignKey(_ n: Notification) { hide() }

    func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) {
        guard let d = m.body as? [String: Any] else { return }
        if d["ready"] != nil {
            ready = true
            if showWhenReady {
                showWhenReady = false
                show()
            }
        } else if d["close"] != nil {
            hide()
        } else if let p = d["press"] as? [String: Any], let page = p["page"] as? String,
                  let key = (p["key"] as? NSNumber)?.intValue {
            hide()
            // the app in front gets the keyboard back first: shortcuts and typing go there
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.06) {
                Service.call("/api/pad/press", method: "POST", body: ["page": page, "key": key]) { _, _ in }
            }
        } else if d["configure"] != nil {
            hide()
            onConfigure?()
        }
    }

    func webView(_ w: WKWebView, decidePolicyFor a: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = a.request.url else { return decisionHandler(.cancel) }
        if url.host == "127.0.0.1" && url.port == opts.port { return decisionHandler(.allow) }
        if url.scheme == "about" || url.scheme == "blob" || url.scheme == "data" { return decisionHandler(.allow) }
        NSWorkspace.shared.open(url)
        decisionHandler(.cancel)
    }

    func webView(_ w: WKWebView, didFinish n: WKNavigation!) { note("pad: loaded \(w.url?.path ?? "")") }
    func webView(_ w: WKWebView, didFailProvisionalNavigation n: WKNavigation!, withError e: Error) { note("pad: \(e)"); retry() }
    func webView(_ w: WKWebView, didFail n: WKNavigation!, withError e: Error) { note("pad: \(e)"); retry() }
    func webViewWebContentProcessDidTerminate(_ w: WKWebView) { note("pad: web process ended"); load() }
}

// MARK: - new versions

/// One notification per new version the service finds on GitHub (update.py); clicking it opens
/// the configurator, which installs it. macOS asks once whether DisplayPad may notify.
final class Notifier: NSObject, UNUserNotificationCenterDelegate {
    var onOpen: (() -> Void)?
    private let told = "notifiedUpdate"

    func attach() { UNUserNotificationCenter.current().delegate = self }  // early: a click may be what started the app

    func announce(_ version: String) {
        guard UserDefaults.standard.string(forKey: told) != version else { return }
        UserDefaults.standard.set(version, forKey: told)
        let center = UNUserNotificationCenter.current()
        center.requestAuthorization(options: [.alert, .sound]) { ok, _ in
            guard ok else { return }
            let c = UNMutableNotificationContent()
            c.title = tr("DisplayPad \(version) is available", "Ya está disponible DisplayPad \(version)")
            c.body = tr("Click to open DisplayPad and update. Your pages and settings stay.",
                        "Haz clic para abrir DisplayPad y actualizar. Tus páginas y ajustes se mantienen.")
            center.add(UNNotificationRequest(identifier: "update", content: c, trigger: nil))
        }
    }

    func userNotificationCenter(_ c: UNUserNotificationCenter, didReceive r: UNNotificationResponse,
                                withCompletionHandler done: @escaping () -> Void) {
        DispatchQueue.main.async { self.onOpen?() }
        done()
    }

    func userNotificationCenter(_ c: UNUserNotificationCenter, willPresent n: UNNotification,
                                withCompletionHandler done: @escaping (UNNotificationPresentationOptions) -> Void) {
        done([.banner, .list])
    }
}

// MARK: - configurator window

final class AppWebView: WKWebView {
    var lastMouseDown: NSEvent?
    override func mouseDown(with event: NSEvent) {
        lastMouseDown = event
        super.mouseDown(with: event)
    }
}

/// The configurator in a window with no browser around it: the page runs up to the top edge,
/// with the window buttons over its header (the page moves its header over for them).
final class Configurator: NSObject, NSWindowDelegate, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler {
    let window: NSWindow
    let web: AppWebView
    var onClose: (() -> Void)?
    private var closing = false
    private var failures = 0
    private let url: URL

    init(url: URL) {
        self.url = url
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1240, height: 840),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                          backing: .buffered, defer: false)
        let conf = WKWebViewConfiguration()
        conf.applicationNameForUserAgent = "DisplayPadApp/\(appVersion)"
        conf.userContentController.addUserScript(WKUserScript(
            source: "document.documentElement.classList.add('in-app')", injectionTime: .atDocumentStart, forMainFrameOnly: true))
        web = AppWebView(frame: .zero, configuration: conf)
        super.init()
        if debugging, #available(macOS 13.3, *) { web.isInspectable = true }
        conf.userContentController.add(WeakHandler(self), name: "dp")
        window.title = "DisplayPad"
        window.titleVisibility = .hidden
        window.titlebarAppearsTransparent = true
        window.toolbar = NSToolbar(identifier: "displaypad")  // a taller title bar: the buttons sit in the page's header
        window.toolbarStyle = .unifiedCompact
        window.titlebarSeparatorStyle = .none
        window.minSize = NSSize(width: 820, height: 520)
        window.isReleasedWhenClosed = false
        window.tabbingMode = .disallowed
        window.collectionBehavior = [.fullScreenPrimary]
        window.backgroundColor = NSColor(name: nil) { a in  // the page's own background, while it loads
            a.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
                ? NSColor(srgbRed: 0x11 / 255, green: 0x11 / 255, blue: 0x14 / 255, alpha: 1)
                : NSColor(srgbRed: 0xF4 / 255, green: 0xF4 / 255, blue: 0xF7 / 255, alpha: 1)
        }
        window.delegate = self
        web.navigationDelegate = self
        web.uiDelegate = self
        web.allowsMagnification = true
        web.setValue(false, forKey: "drawsBackground")
        window.contentView = web
        if !window.setFrameUsingName("DisplayPadConfigurator") { window.center() }
        window.setFrameAutosaveName("DisplayPadConfigurator")
        web.load(URLRequest(url: url))
    }

    // ------------------------------------------------ from the page
    func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) {
        guard let d = m.body as? [String: Any] else { return }
        if d["drag"] != nil, let e = web.lastMouseDown, e.window === window {  // the header moves the window
            window.performDrag(with: e)
        } else if d["zoom"] != nil {  // a double click on the header, like on a title bar
            switch UserDefaults.standard.string(forKey: "AppleActionOnDoubleClick") ?? "Maximize" {
            case "Minimize": window.performMiniaturize(nil)
            case "None": break
            default: window.performZoom(nil)
            }
        } else if let theme = d["theme"] as? String {  // the page's theme, for the window buttons
            window.appearance = theme == "dark" ? NSAppearance(named: .darkAqua) : theme == "light" ? NSAppearance(named: .aqua) : nil
        }
    }

    // ------------------------------------------------ unsaved changes
    /// Runs proceed() unless the page has unsaved changes and the person cancels.
    func guardUnsaved(_ proceed: @escaping () -> Void) {
        web.evaluateJavaScript("typeof isDirty === 'function' && isDirty()") { [weak self] value, _ in
            guard let self = self else { return }
            guard (value as? Bool) == true else { return proceed() }
            let a = NSAlert()
            a.messageText = tr("Save your changes to the keys?", "¿Guardar los cambios en las teclas?")
            a.informativeText = tr("If you don't save them, they are lost.", "Si no los guardas, se pierden.")
            a.addButton(withTitle: tr("Save", "Guardar"))
            a.addButton(withTitle: tr("Cancel", "Cancelar"))
            let dont = a.addButton(withTitle: tr("Don't Save", "No guardar"))
            dont.keyEquivalent = "d"
            dont.keyEquivalentModifierMask = .command
            a.beginSheetModal(for: self.window) { r in
                switch r {
                case .alertFirstButtonReturn:
                    self.web.callAsyncJavaScript("await save(); return !isDirty()", arguments: [:], in: nil, in: .page) { res in
                        if case .success(let ok) = res, (ok as? Bool) == true { proceed() }
                    }
                case .alertThirdButtonReturn: proceed()
                default: break
                }
            }
        }
    }

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        if closing { return true }
        guardUnsaved { [weak self] in
            self?.closing = true
            self?.window.close()
        }
        return false
    }

    func windowWillClose(_ n: Notification) {
        web.stopLoading()
        onClose?()
    }

    func reload() { guardUnsaved { [weak self] in self?.web.reload() } }

    // ------------------------------------------------ links, files and dialogs
    func webView(_ w: WKWebView, decidePolicyFor a: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let u = a.request.url else { return decisionHandler(.cancel) }
        if (u.host == "127.0.0.1" || u.host == "localhost") && u.port == opts.port { return decisionHandler(.allow) }
        if u.scheme == "about" || u.scheme == "blob" || u.scheme == "data" { return decisionHandler(.allow) }
        NSWorkspace.shared.open(u)  // the README, System Settings…: where they belong
        decisionHandler(.cancel)
    }

    func webView(_ w: WKWebView, createWebViewWith c: WKWebViewConfiguration, for a: WKNavigationAction,
                 windowFeatures f: WKWindowFeatures) -> WKWebView? {
        if let u = a.request.url { NSWorkspace.shared.open(u) }
        return nil
    }

    func webView(_ w: WKWebView, didFinish n: WKNavigation!) {
        failures = 0
        note("configurator: loaded \(w.url?.path ?? "")")
        if window.styleMask.contains(.fullScreen) { fullScreen(true) }
    }

    // no window buttons in full screen: the header moves back to the edge
    func windowWillEnterFullScreen(_ n: Notification) { fullScreen(true) }
    func windowWillExitFullScreen(_ n: Notification) { fullScreen(false) }
    private func fullScreen(_ on: Bool) {
        web.evaluateJavaScript("document.documentElement.classList.toggle('fullscreen', \(on))", completionHandler: nil)
    }

    func webView(_ w: WKWebView, didFailProvisionalNavigation n: WKNavigation!, withError e: Error) {
        note("configurator: \(e)")
        failures += 1  // the service restarting: try again for a while
        if failures <= 20 {
            DispatchQueue.main.asyncAfter(deadline: .now() + 1) { [weak self] in
                guard let self = self else { return }
                self.web.load(URLRequest(url: Service.pageURL("/") ?? self.url))
            }
        }
    }

    func webViewWebContentProcessDidTerminate(_ w: WKWebView) { note("configurator: web process ended"); w.reload() }

    func webView(_ w: WKWebView, runOpenPanelWith p: WKOpenPanelParameters, initiatedByFrame f: WKFrameInfo,
                 completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = p.allowsMultipleSelection
        panel.canChooseDirectories = p.allowsDirectories
        panel.canChooseFiles = true
        panel.beginSheetModal(for: window) { r in completionHandler(r == .OK ? panel.urls : nil) }
    }

    func webView(_ w: WKWebView, runJavaScriptAlertPanelWithMessage msg: String, initiatedByFrame f: WKFrameInfo,
                 completionHandler: @escaping () -> Void) {
        let a = NSAlert()
        a.messageText = msg
        a.beginSheetModal(for: window) { _ in completionHandler() }
    }

    func webView(_ w: WKWebView, runJavaScriptConfirmPanelWithMessage msg: String, initiatedByFrame f: WKFrameInfo,
                 completionHandler: @escaping (Bool) -> Void) {
        let a = NSAlert()
        a.messageText = msg
        a.addButton(withTitle: "OK")
        a.addButton(withTitle: tr("Cancel", "Cancelar"))
        a.beginSheetModal(for: window) { r in completionHandler(r == .alertFirstButtonReturn) }
    }

    func webView(_ w: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String, defaultText: String?,
                 initiatedByFrame f: WKFrameInfo, completionHandler: @escaping (String?) -> Void) {
        let a = NSAlert()
        a.messageText = prompt
        let field = NSTextField(frame: NSRect(x: 0, y: 0, width: 300, height: 24))
        field.stringValue = defaultText ?? ""
        a.accessoryView = field
        a.addButton(withTitle: "OK")
        a.addButton(withTitle: tr("Cancel", "Cancelar"))
        a.beginSheetModal(for: window) { r in completionHandler(r == .alertFirstButtonReturn ? field.stringValue : nil) }
    }
}

// MARK: - the app

final class AppDelegate: NSObject, NSApplicationDelegate {
    let pad = FloatingPad()
    let hotkey = Hotkey()
    let notifier = Notifier()
    var configurator: Configurator?
    var popupRev = -1
    var popupOn = false
    var waitFailures = 0

    func applicationDidFinishLaunching(_ n: Notification) {
        NSApp.mainMenu = makeMenu()
        #if DEBUG_HOOKS
        installTestHooks()
        #endif
        Hotkey.onPress = { [weak self] in self?.pad.toggle() }
        pad.onConfigure = { [weak self] in self?.openConfigurator() }
        notifier.onOpen = { [weak self] in self?.openConfigurator() }
        notifier.attach()
        pad.load()
        waitForService()
        if opts.popup { pad.show() }
        if !opts.background { openConfigurator() }
    }

    func applicationShouldHandleReopen(_ s: NSApplication, hasVisibleWindows: Bool) -> Bool {
        openConfigurator()
        return false
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ s: NSApplication) -> Bool { false }

    func applicationSupportsSecureRestorableState(_ app: NSApplication) -> Bool { true }

    // ------------------------------------------------ the service's news
    func waitForService() {
        Service.call("/api/popup/wait?rev=\(popupRev)&hotkey=\(hotkey.state)", timeout: 45) { [weak self] code, obj in
            guard let self = self else { return }
            if code == 200, let o = obj {
                self.waitFailures = 0
                if let p = o["popup"] as? [String: Any] { self.apply(p) }
                if (o["event"] as? String) == "show" { self.pad.toggle() }
                self.waitForService()
            } else {  // restarting, or not there yet (at login)
                self.waitFailures += 1
                DispatchQueue.main.asyncAfter(deadline: .now() + min(5, 0.5 * Double(self.waitFailures))) { self.waitForService() }
            }
        }
    }

    func apply(_ p: [String: Any]) {
        if let lang = p["language"] as? String, lang != language {
            language = lang
            NSApp.mainMenu = makeMenu()
        }
        if let v = p["update"] as? String { notifier.announce(v) }
        let rev = (p["rev"] as? NSNumber)?.intValue ?? -1
        guard rev != popupRev else { return }
        popupRev = rev
        popupOn = (p["enabled"] as? Bool) ?? false
        if popupOn, (p["kind"] as? String) == "key", let code = (p["code"] as? NSNumber)?.uint32Value {
            hotkey.set(code: code, mods: (p["carbon"] as? NSNumber)?.uint32Value ?? 0)
        } else {
            hotkey.set(code: nil, mods: 0)
        }
        if !popupOn {
            pad.hide()
            if configurator == nil { NSApp.terminate(nil) }  // nothing left to do
        }
    }

    // ------------------------------------------------ configurator
    func openConfigurator() {
        if let c = configurator { return bringUp(c) }
        Service.ensureUp { [weak self] up in
            guard let self = self else { return }
            guard up else {
                return self.fail(tr("The service is not responding. Check the log in ~/Library/Logs/DisplayPadMac.log or run install.sh again.",
                                    "El servicio no responde. Revisa el registro en ~/Library/Logs/DisplayPadMac.log o vuelve a ejecutar install.sh."))
            }
            guard let url = Service.pageURL("/") else {
                return self.fail(tr("The configurator key was not found. Run install.sh again.",
                                    "No se encontró la clave del configurador. Vuelve a ejecutar install.sh."))
            }
            if let c = self.configurator { return self.bringUp(c) }  // asked twice while the service started
            let c = Configurator(url: url)
            c.onClose = { [weak self] in self?.configuratorClosed() }
            self.configurator = c
            self.bringUp(c)
        }
    }

    /// The window in front, with a Dock icon and the menu bar. Opened by another process (the
    /// pad's Configure key goes through the service) macOS may keep the app in the back; the
    /// window still comes up over the others.
    func bringUp(_ c: Configurator) {
        NSApp.setActivationPolicy(.regular)
        if c.window.isMiniaturized { c.window.deminiaturize(nil) }
        c.window.makeKeyAndOrderFront(nil)
        c.window.orderFrontRegardless()
        activate()
        DispatchQueue.main.async { self.activate() }  // once the Dock icon is there
    }

    func configuratorClosed() {
        configurator = nil
        if !popupOn { return NSApp.terminate(nil) }
        NSApp.setActivationPolicy(.accessory)  // keeps waiting for the floating pad, without a Dock icon
    }

    func activate() {
        NSApp.activate(ignoringOtherApps: true)  // (NSApp.activate() alone yields to the app in front)
    }

    func fail(_ msg: String) {
        NSApp.setActivationPolicy(.regular)
        activate()
        let a = NSAlert()
        a.alertStyle = .critical
        a.messageText = "DisplayPad"
        a.informativeText = msg
        a.runModal()
        if configurator == nil {
            if popupOn { NSApp.setActivationPolicy(.accessory) } else { NSApp.terminate(nil) }
        }
    }

    // ------------------------------------------------ menus
    @objc func quit(_ sender: Any?) {
        if let c = configurator { return c.window.performClose(nil) }  // and with the floating pad off, the app quits
        if popupOn { NSApp.setActivationPolicy(.accessory) } else { NSApp.terminate(nil) }
    }

    @objc func showSettings(_ sender: Any?) {
        openConfigurator()
        configurator?.web.evaluateJavaScript("typeof setView === 'function' && setView('settings')", completionHandler: nil)
    }

    @objc func reloadPage(_ sender: Any?) { configurator?.reload() }
    @objc func actualSize(_ sender: Any?) { configurator?.web.pageZoom = 1 }
    @objc func zoomIn(_ sender: Any?) { if let w = configurator?.web { w.pageZoom = min(3, w.pageZoom + 0.1) } }
    @objc func zoomOut(_ sender: Any?) { if let w = configurator?.web { w.pageZoom = max(0.5, w.pageZoom - 0.1) } }

    @objc func openInBrowser(_ sender: Any?) {
        if let u = Service.pageURL("/") { NSWorkspace.shared.open(u) }
    }

    @objc func showPad(_ sender: Any?) { pad.show() }

    @objc func openHelp(_ sender: Any?) {
        NSWorkspace.shared.open(URL(string: repoURL + (language == "es" ? "/blob/main/README.es.md" : "#readme"))!)
    }

    func makeMenu() -> NSMenu {
        func item(_ title: String, _ action: Selector?, _ key: String = "", _ mods: NSEvent.ModifierFlags = .command,
                  mine: Bool = false) -> NSMenuItem {
            let i = NSMenuItem(title: title, action: action, keyEquivalent: key)
            i.keyEquivalentModifierMask = mods
            if mine { i.target = self }
            return i
        }
        func menu(_ title: String, _ items: [NSMenuItem]) -> NSMenuItem {
            let m = NSMenu(title: title)
            items.forEach { m.addItem($0) }
            let top = NSMenuItem(title: title, action: nil, keyEquivalent: "")
            top.submenu = m
            return top
        }
        let main = NSMenu()
        main.addItem(menu("DisplayPad", [
            item(tr("About DisplayPad", "Acerca de DisplayPad"), #selector(NSApplication.orderFrontStandardAboutPanel(_:))),
            .separator(),
            item(tr("Settings…", "Ajustes…"), #selector(showSettings(_:)), ",", mine: true),
            item(tr("Show the Floating Pad", "Mostrar el pad flotante"), #selector(showPad(_:)), mine: true),
            .separator(),
            item(tr("Hide DisplayPad", "Ocultar DisplayPad"), #selector(NSApplication.hide(_:)), "h"),
            item(tr("Hide Others", "Ocultar otros"), #selector(NSApplication.hideOtherApplications(_:)), "h", [.command, .option]),
            item(tr("Show All", "Mostrar todo"), #selector(NSApplication.unhideAllApplications(_:))),
            .separator(),
            item(tr("Quit DisplayPad", "Salir de DisplayPad"), #selector(quit(_:)), "q", mine: true),
        ]))
        main.addItem(menu(tr("File", "Archivo"), [
            item(tr("Close Window", "Cerrar ventana"), #selector(NSWindow.performClose(_:)), "w"),
        ]))
        main.addItem(menu(tr("Edit", "Edición"), [
            item(tr("Undo", "Deshacer"), Selector(("undo:")), "z"),
            item(tr("Redo", "Rehacer"), Selector(("redo:")), "z", [.command, .shift]),
            .separator(),
            item(tr("Cut", "Cortar"), #selector(NSText.cut(_:)), "x"),
            item(tr("Copy", "Copiar"), #selector(NSText.copy(_:)), "c"),
            item(tr("Paste", "Pegar"), #selector(NSText.paste(_:)), "v"),
            item(tr("Select All", "Seleccionar todo"), #selector(NSText.selectAll(_:)), "a"),
        ]))
        main.addItem(menu(tr("View", "Visualización"), [
            item(tr("Reload", "Volver a cargar"), #selector(reloadPage(_:)), "r", mine: true),
            .separator(),
            item(tr("Actual Size", "Tamaño real"), #selector(actualSize(_:)), "0", mine: true),
            item(tr("Zoom In", "Ampliar"), #selector(zoomIn(_:)), "=", mine: true),
            item(tr("Zoom Out", "Reducir"), #selector(zoomOut(_:)), "-", mine: true),
            .separator(),
            item(tr("Open in Browser", "Abrir en el navegador"), #selector(openInBrowser(_:)), mine: true),
            .separator(),
            item(tr("Enter Full Screen", "Pantalla completa"), #selector(NSWindow.toggleFullScreen(_:)), "f", [.command, .control]),
        ]))
        let window = menu(tr("Window", "Ventana"), [
            item(tr("Minimize", "Minimizar"), #selector(NSWindow.performMiniaturize(_:)), "m"),
            item(tr("Zoom", "Zoom"), #selector(NSWindow.performZoom(_:))),
            .separator(),
            item(tr("Bring All to Front", "Traer todo al frente"), #selector(NSApplication.arrangeInFront(_:))),
        ])
        main.addItem(window)
        NSApp.windowsMenu = window.submenu
        let help = menu(tr("Help", "Ayuda"), [item(tr("DisplayPad Help", "Ayuda de DisplayPad"), #selector(openHelp(_:)), "?", mine: true)])
        main.addItem(help)
        NSApp.helpMenu = help.submenu
        return main
    }
}

#if DEBUG_HOOKS
// Test builds only (launcher/build.sh with SWIFT_FLAGS="-D DEBUG_HOOKS"): another process drives
// the app with distributed notifications named "<bundle id>.test", object = a command; results go
// to stderr.
extension AppDelegate {
    func installTestHooks() {
        let name = Notification.Name((Bundle.main.bundleIdentifier ?? "displaypad") + ".test")
        DistributedNotificationCenter.default().addObserver(forName: name, object: nil, queue: .main) { [weak self] n in
            guard let self = self, let cmd = n.object as? String else { return }
            let (verb, arg) = cmd.firstIndex(of: " ").map { (String(cmd[..<$0]), String(cmd[cmd.index(after: $0)...])) } ?? (cmd, "")
            func say(_ s: String) { FileHandle.standardError.write("test \(verb): \(s)\n".data(using: .utf8)!) }
            switch verb {
            case "js", "padjs":
                let web: WKWebView? = verb == "js" ? self.configurator?.web : self.pad.web
                web?.evaluateJavaScript(arg) { v, e in say(e.map { "\($0)" } ?? "\(v ?? "nil")") }
            case "close": self.configurator?.window.performClose(nil); say("sent")
            case "quit": self.quit(nil); say("sent")
            case "open": self.openConfigurator(); say("sent")
            case "front": self.configurator?.window.orderFrontRegardless(); say("sent")
            case "padshow", "size":  // on the sharpest screen (pictures for the README)
                let screen = NSScreen.screens.max { $0.backingScaleFactor < $1.backingScaleFactor } ?? NSScreen.screens[0]
                let f = screen.visibleFrame
                if verb == "padshow" { self.pad.show(at: NSPoint(x: f.midX, y: f.midY)); return say("sent") }
                let n = arg.split(separator: " ").compactMap { Double($0) }
                guard n.count == 2, let w = self.configurator?.window else { return say("size W H, with the window open") }
                w.setFrame(NSRect(x: (f.midX - n[0] / 2).rounded(), y: (f.midY - n[1] / 2).rounded(), width: n[0], height: n[1]), display: true)
                say("\(w.windowNumber) scale=\(screen.backingScaleFactor)")
            case "ids":
                say("window=\(self.configurator?.window.windowNumber ?? 0) pad=\(self.pad.panel.windowNumber)")
            case "sheet":
                func buttons(_ v: NSView) -> [NSButton] { (v as? NSButton).map { [$0] } ?? v.subviews.flatMap(buttons) }
                let found = self.configurator?.window.attachedSheet.flatMap { $0.contentView.map(buttons) }?.first { $0.title == arg }
                say(found == nil ? "no button '\(arg)'" : "pressed")
                found?.performClick(nil)
            case "state":
                let sheet = self.configurator?.window.attachedSheet
                let texts = sheet?.contentView.map { v -> [String] in
                    func walk(_ v: NSView) -> [String] { ((v as? NSTextField).map { [$0.stringValue] } ?? []) + v.subviews.flatMap(walk) }
                    return walk(v).filter { !$0.isEmpty }
                } ?? []
                say("policy=\(NSApp.activationPolicy().rawValue) window=\(self.configurator != nil) " +
                    "pad=\(self.pad.panel.isVisible) sheet=\(texts)")
            default: say("unknown")
            }
        }
    }
}
#endif

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
