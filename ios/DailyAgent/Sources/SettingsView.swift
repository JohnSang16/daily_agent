import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var state: AppState
    @State private var url = Keychain.get("baseURL") ?? ""
    @State private var token = Keychain.get("token") ?? ""
    @State private var status = ""

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 28) {
                BigTitle(text: "Settings")
                VStack(alignment: .leading, spacing: 10) {
                    sectionLabel("agent address")
                    field(TextField("http://100.x.x.x:8000", text: $url))
                    sectionLabel("token")
                    field(SecureField("bearer token", text: $token))
                    HStack {
                        PillButton(label: "save and test", primary: true) {
                            state.saveConnection(url: url, token: token)
                            status = "checking."
                            Task {
                                await state.refresh()
                                status = state.problem ?? (state.offline ? "could not reach the agent." : "connected.")
                            }
                        }
                        Text(status).font(.system(size: 12.5)).foregroundStyle(Theme.secondary)
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
            }
            .padding(.horizontal, 24).padding(.top, 72).padding(.bottom, 60)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
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
