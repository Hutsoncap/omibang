import QtQuick
import qs.Ui

BarWidget {
  id: root
  moduleName: "omarchy.menu"

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    hasVisualContent: true
    labelVisible: false
    fixedWidth: barSize
    onPressed: function(button) {
      if (!root.bar) return
      if (button === Qt.RightButton) root.bar.run("xdg-terminal-exec")
      else root.bar.run("omarchy-shell shell toggle omarchy.menu '{\"menu\":\"root\"}'")
    }

    Item {
      id: logo
      anchors.centerIn: parent
      readonly property int cellSize: Math.max(3, Math.round(button.fontSize / 3))
      width: cellSize * 3
      height: width

      property color logoColor: button.active && button.useActiveColor
        ? button.activeColor
        : button.foreground

      Rectangle {
        width: logo.cellSize
        height: logo.height
        color: logo.logoColor
      }

      Rectangle {
        x: logo.cellSize
        y: logo.cellSize
        width: logo.cellSize
        height: logo.cellSize
        color: logo.logoColor
      }

      Rectangle {
        x: logo.cellSize * 2
        y: logo.cellSize * 2
        width: logo.cellSize
        height: logo.cellSize
        color: logo.logoColor
      }
    }
  }
}
