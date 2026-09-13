<?php

$store = $_GET['id'] ?? '';
$product = $_GET['product'] ?? '';

if ($store == '' || $product == '') {
    echo "Thieu Store ID hoac Product ID";
    exit;
}

$csv_file = $store . ".csv";

if (!file_exists($csv_file)) {
    echo "Khong tim thay file: " . $csv_file;
    exit;
}

$file = fopen($csv_file, "r");

$header = fgetcsv($file, 0, ",", '"', "\\");

$found = false;
while (($row = fgetcsv($file, 0, ",", '"', "\\")) !== false) {

    $product_id = trim($row[0]);

    if ($product_id == $product) {

        echo "Store ID: " . $store . "<br>";
        echo "Product ID: " . $row[0] . "<br>";
        echo "Ten san pham: " . $row[1] . "<br>";
        echo "Gia: " . $row[2] . " VND<br>";
        echo "Vi tri: " . $row[3] . "<br>";
        echo "Han su dung: " . $row[4] . "<br>";

        $found = true;
        break;
    }
}

if (!$found) {
    echo "Khong tim thay san pham: " . $product;
}

fclose($file);

?>
