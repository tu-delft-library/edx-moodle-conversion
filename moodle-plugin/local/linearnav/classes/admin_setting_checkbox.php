<?php
// This file is part of Moodle - http://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// Moodle is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with Moodle.  If not, see <http://www.gnu.org/licenses/>.

/**
 * Admin checkbox without the "Default: ..." line.
 *
 * @package    local_linearnav
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

namespace local_linearnav;

/**
 * Same as admin_setting_configcheckbox, minus the default info under it.
 */
class admin_setting_checkbox extends \admin_setting_configcheckbox {
    #[\Override]
    public function output_html($data, $query = '') {
        global $OUTPUT;

        $element = $OUTPUT->render_from_template('core_admin/setting_configcheckbox', [
            'id' => $this->get_id(),
            'name' => $this->get_full_name(),
            'no' => $this->no,
            'value' => $this->yes,
            'checked' => (string) $data === $this->yes,
            'readonly' => $this->is_readonly(),
        ]);
        return format_admin_setting($this, $this->visiblename, $element, $this->description, true, '', null, $query);
    }
}
