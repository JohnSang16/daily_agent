import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var state: AppState
    @State private var url = Keychain.get("baseURL") ?? ""
    @State private var token = Keychain.get("token") ?? ""
    @State private var status = ""
    @State private var checking = false
    @State private var nightly = UserDefaults.standard.bool(forKey: "nightlyCheckin")
    @State private var nightlyNote = ""
    @FocusState private var focused: Field?
    private enum Field { case url, token }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 28) {
                BigTitle(text: "Settings")
                VStack(alignment: .leading, spacing: 10) {
                    sectionLabel("agent address")
                    field(urlField.focused($focused, equals: .url)
                        .submitLabel(.next).onSubmit { focused = .token })
                    sectionLabel("token")
                    field(SecureField("bearer token", text: $token).focused($focused, equals: .token).submitLabel(.done))
                    HStack {
                        PillButton(label: checking ? "checking" : "save and test", primary: true,
                                   enabled: !checking && !url.trimmingCharacters(in: .whitespaces).isEmpty && !token.isEmpty) {
                            focused = nil
                            state.saveConnection(url: url, token: token)
                            url = Keychain.get("baseURL") ?? url  // show the cleaned up address
                            guard state.configured else { status = "that address does not look right."; return }
                            status = ""; checking = true
                            Task {
                                await state.refresh()
                                checking = false
                                status = state.problem ?? (state.offline ? "could not reach the agent." : "connected.")
                            }
                        }
                        if checking { ProgressView().controlSize(.small).tint(Theme.secondary) }
                        Text(status).font(.system(size: 12.5)).foregroundStyle(Theme.secondary).contentTransition(.opacity)
                    }
                    Text("stored in the keychain on this phone only.").font(.system(size: 12.5)).foregroundStyle(Theme.tertiary)
                }
                VStack(alignment: .leading, spacing: 10) {
                    sectionLabel("reminders")
                    Text("sends the title, due date and done state of your open reminders to the agent. nothing is changed in reminders.")
                        .font(.system(size: 13.5)).foregroundStyle(Theme.secondary)
                    PillButton(label: "upload reminders") { Task { await state.uploadReminders() } }
                    Text(state.reminderStatus).font(.system(size: 12.5)).foregroundStyle(Theme.secondary)
                }
                VStack(alignment: .leading, spacing: 10) {
                    sectionLabel("nightly check-in")
                    Toggle(isOn: $nightly) {
                        Text("9 pm reminder: did #1 happen?").font(.system(size: 15)).foregroundStyle(Theme.body)
                    }
                    .tint(Theme.toggle).frame(minHeight: 44)
                    .onChange(of: nightly) { _, on in
                        Task {
                            let ok = await state.setNightlyReminder(on)
                            if !ok { nightly = false; nightlyNote = "notifications are off for js ai. turn them on in iOS settings." }
                            else { nightlyNote = "" }
                        }
                    }
                    if !nightlyNote.isEmpty { Text(nightlyNote).font(.system(size: 12.5)).foregroundStyle(Theme.secondary) }
                    Text("a local reminder on this phone. nothing is sent anywhere.").font(.system(size: 12.5)).foregroundStyle(Theme.tertiary)
                }
                Text("js ai " + (Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? ""))
                    .font(.system(size: 12)).foregroundStyle(Theme.tertiary)
            }
            .page()
            .animation(Theme.ease, value: status)
        }
        .scrollDismissesKeyboard(.interactively)
    }

    private var urlField: some View {
        #if os(iOS)
        TextField("http://100.x.x.x:8000", text: $url).keyboardType(.URL)
        #else
        TextField("http://100.x.x.x:8000", text: $url)
        #endif
    }

    @ViewBuilder
    private func field<V: View>(_ v: V) -> some View {
        v.font(.system(size: 16)).foregroundStyle(Theme.title)
            .padding(.horizontal, 18).frame(minHeight: 48).glass(Capsule())
            #if os(iOS)
            .textInputAutocapitalization(.never).autocorrectionDisabled()
            #endif
    }
}
