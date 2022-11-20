"use strict";

/**
 *
 * @function onload
 * @description  after page has loaded initialize all treeitems based on the role=treeitem
 */

function addTreeItemsFunctionality() {
  var treeitems = document.querySelectorAll('[role="treeitem"]');
  for (var i = 0; i < treeitems.length; i++) {
    treeitems[i].addEventListener("click", function (event) {
      var appendPermCheck = document.getElementById("appendPermCheck");
      var writePermCheck = document.getElementById("writePermCheck");
      var readPermCheck = document.getElementById("readPermCheck");
      var overwritePermCheck = document.getElementById("overwritePermCheck");
      var listPermCheck = document.getElementById("listPermCheck");
      var renameFilesPermCheck = document.getElementById("renameFilesPermCheck");
      var deleteFilesPermCheck = document.getElementById("deleteFilesPermCheck");
      var checksumPermCheck = document.getElementById("checksumPermCheck");
      var shareFilesPermCheck = document.getElementById("shareFilesPermCheck");
      var createPermCheck = document.getElementById("createPermCheck");
      var renamePermCheck = document.getElementById("renamePermCheck");
      var deletePermCheck = document.getElementById("deletePermCheck");
      var sharePermCheck = document.getElementById("sharePermCheck");
      var applySubPermCheck = document.getElementById("applySubPermCheck");
      var confirmedByAdmin = document.getElementById("confirmedByAdmin");

      var absolutePath1 = document.getElementById("absolute-path-1");
      var absolutePath2 = document.getElementById("absolute-path-2");
      var parentId = document.getElementById("parent-id");
      var currentDirId = document.getElementById("current-dir-id");
      var currentDirName = document.getElementById("current-dir-name");
      var indexCode = document.getElementById("index-code");
      var subDirPermCheck = document.getElementById("subDirPermCheck");

      var treeitem = event.currentTarget;
      var uid = document.getElementById("current-user-id").innerHTML;
      var did = treeitem.getAttribute("current-dir-id");
      var dname = treeitem.getAttribute("current-dir-name");
      var path = treeitem.getAttribute("absolute-path");
      var pid = treeitem.getAttribute("parent-id");
      var index = treeitem.getAttribute("indexcode");
      currentDirId.innerHTML = did;
      currentDirName.innerHTML = dname;
      parentId.innerHTML = pid;
      indexCode.innerHTML = index;
      if (subDirPermCheck) {
        if (index < -2) {
          subDirPermCheck.disabled = false;
        } else {
          subDirPermCheck.disabled = true;
        }
      }
      absolutePath1.innerHTML = path + '/{<span class="text-danger">NEW</span>}';
      absolutePath2.innerHTML = path;
      getPermissions(uid);

      event.stopPropagation();
      event.preventDefault();
    });
  }
}

function getPermissions(uid) {
  var did = document.getElementById("current-dir-id").innerHTML;
  var currentUserId = document.getElementById("current-user-id");
  currentUserId.innerHTML = uid;

  var appendPermCheck = document.getElementById("appendPermCheck");
  var writePermCheck = document.getElementById("writePermCheck");
  var readPermCheck = document.getElementById("readPermCheck");
  var overwritePermCheck = document.getElementById("overwritePermCheck");
  var listPermCheck = document.getElementById("listPermCheck");
  var renameFilesPermCheck = document.getElementById("renameFilesPermCheck");
  var deleteFilesPermCheck = document.getElementById("deleteFilesPermCheck");
  var checksumPermCheck = document.getElementById("checksumPermCheck");
  var shareFilesPermCheck = document.getElementById("shareFilesPermCheck");
  var createPermCheck = document.getElementById("createPermCheck");
  var renamePermCheck = document.getElementById("renamePermCheck");
  var deletePermCheck = document.getElementById("deletePermCheck");
  var sharePermCheck = document.getElementById("sharePermCheck");
  var applySubPermCheck = document.getElementById("applySubPermCheck");
  var subDirPermCheck = document.getElementById("subDirPermCheck");
  var confirmedByAdmin = document.getElementById("confirmedByAdmin");

  var url = "/mftuser/" + uid + "/permissions/" + did + "/";
  fetch(url, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "XMLHttpRequest",
    },
  })
    .then((Result) => Result.json())
    .then((string) => {
      appendPermCheck.checked = false;
      writePermCheck.checked = false;
      readPermCheck.checked = false;
      overwritePermCheck.checked = false;
      listPermCheck.checked = false;
      renameFilesPermCheck.checked = false;
      deleteFilesPermCheck.checked = false;
      checksumPermCheck.checked = false;
      shareFilesPermCheck.checked = false;
      sharePermCheck.checked = false;
      createPermCheck.checked = false;
      renamePermCheck.checked = false;
      deletePermCheck.checked = false;
      applySubPermCheck.checked = false;
      if (subDirPermCheck) {
        subDirPermCheck.checked = false;
      }
      string.forEach((perm) => {
        if (perm.value == 1024) {
          // Append
          appendPermCheck.checked = true;
        } else if (perm.value == 2) {
          // Upload (Write)
          writePermCheck.checked = true;
        } else if (perm.value == 1) {
          // Download (Read)
          readPermCheck.checked = true;
        } else if (perm.value == 512) {
          // Overwrit
          overwritePermCheck.checked = true;
        } else if (perm.value == 256) {
          // List
          listPermCheck.checked = true;
        } else if (perm.value == 8) {
          // Rename Files
          renameFilesPermCheck.checked = true;
        } else if (perm.value == 32) {
          // Delete Files
          deleteFilesPermCheck.checked = true;
        } else if (perm.value == 128) {
          // Checksum
          checksumPermCheck.checked = true;
        } else if (perm.value == 4096) {
          // Share File
          shareFilesPermCheck.checked = true;
        } else if (perm.value == 0) {
          // Apply To Subfolders
          applySubPermCheck.checked = true;
          if (subDirPermCheck) {
            subDirPermCheck.checked = true;
          }
        } else if (perm.value == 4) {
          // Create
          createPermCheck.checked = true;
        } else if (perm.value == 16) {
          // Rename
          renamePermCheck.checked = true;
        } else if (perm.value == 64) {
          // Delete
          deletePermCheck.checked = true;
        } else if (perm.value == 2048) {
          // Share
          sharePermCheck.checked = true;
        } else if (perm.value == "notconfirmed") {
          // hide confirmed label
          confirmedByAdmin.setAttribute("style", "display: none");
        } else if (perm.value == "isconfirmed") {
          // show confirmed label
          confirmedByAdmin.removeAttribute("style");
        }
      });
    })
    .catch((errorMsg) => {
      console.log(errorMsg);
    });
}

function cleanInputValue(input, type) {
  if (type == "name") {
    input = input.replace(/[\u0600-\u06FF]/g, "");
  } else if (type == "number") {
    input = input.replace(/[a-z]/g, "");
    input = input.replace(/[A-Z]/g, "");
    input = input.replace(/\_/g, "");
    input = input.replace(/\-/g, "");
  } else if (type == "alias") {
    input = input.replace(/[\u0600-\u06FF]/g, "");
  }
  if (type != "alias" && type != "name") {
    input = input.replace(/\_/g, "");
    input = input.replace(/\-/g, "");
  }
  input = input.replace(/\@/g, "");
  input = input.replace(/\#/g, "");
  input = input.replace(/\!/g, "");
  input = input.replace(/\$/g, "");
  input = input.replace(/\%/g, "");
  input = input.replace(/\^/g, "");
  input = input.replace(/\&/g, "");
  input = input.replace(/\*/g, "");
  input = input.replace(/\(/g, "");
  input = input.replace(/\)/g, "");
  input = input.replace(/\[/g, "");
  input = input.replace(/\]/g, "");
  input = input.replace(/\{/g, "");
  input = input.replace(/\}/g, "");
  input = input.replace(/\+/g, "");
  input = input.replace(/\=/g, "");
  input = input.replace(/\//g, "");
  input = input.replace(/\\/g, "");
  input = input.replace(/\|/g, "");
  input = input.replace(/\~/g, "");
  input = input.replace(/\'/g, "");
  input = input.replace(/\`/g, "");
  input = input.replace(/\"/g, "");
  input = input.replace(/\,/g, "");
  input = input.replace(/\./g, "");
  input = input.replace(/\?/g, "");
  input = input.replace(/\;/g, "");
  input = input.replace(/\:/g, "");
  input = input.replace(/\>/g, "");
  input = input.replace(/\</g, "");
  return input;
}

function goBack() {
  var url = "/";
  window.location = url;
}

window.addEventListener("load", function () {
  addTreeItemsFunctionality();
});
