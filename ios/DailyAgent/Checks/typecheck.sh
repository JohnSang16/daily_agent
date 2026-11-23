#!/bin/sh
# Typechecks the SwiftUI screens without Xcode: the command line tools lack the SwiftUI macro plugin,
# so @State is swapped for a stand in wrapper with the same surface. Not a substitute for running the app.
set -e
cd "$(dirname "$0")/.."
out=$(mktemp -d)
for f in Sources/*.swift; do
    sed -e 's/@State /@StandInState /g' -e 's/= State(initialValue:/= StandInState(wrappedValue:/g' "$f" > "$out/$(basename "$f")"
done
cat > "$out/_StandIn.swift" <<'SWIFT'
import SwiftUI
@propertyWrapper struct StandInState<V>: DynamicProperty {
    private final class Box { var v: V; init(_ v: V) { self.v = v } }
    private let box: Box
    init(wrappedValue: V) { box = Box(wrappedValue) }
    var wrappedValue: V { get { box.v } nonmutating set { box.v = newValue } }
    var projectedValue: Binding<V> { Binding(get: { box.v }, set: { box.v = $0 }) }
}
SWIFT
swiftc -typecheck -swift-version 5 -target arm64-apple-macos26.0 "$out"/*.swift
rm -rf "$out"
echo "typecheck passed"
