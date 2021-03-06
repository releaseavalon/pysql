# coding = utf8
# mysql for test ip:118.24.5.150 user:admin pass:admin
import pymysql
from lxml import etree
import time
import copy
# 使用 with codecs.open(path, "w", "utf-8")as f: 格式保存结果防止乱码
import codecs


class SchemaGenerator:
    """read a xml file and give each node a special id"""
    def __init__(self):
        pass

    def __init__(self, path):
        self.LoadXML(path)
        self.counter = 1
        self.result = ["ID ParentID ElementName OrderID DataType \r\n"]
    
    def LoadXML(self, path):
        self.xmltree = etree.parse(path)

    def generate(self, node, parent_node_id, order):
        if len(node) == 0:
            s = str(self.counter) + " " + str(parent_node_id) + " " + node.tag + " " + str(order) + " Data \r\n"
            self.result.append(s)
            self.counter += 1
            return
        else:
            if node[0].tag == "array":
                s = str(self.counter) + " " + str(parent_node_id) + " " + node.tag + " " + str(order) + " Array \r\n"
                self.result.append(s)
                self.counter += 1
                return
            else:
                s = str(self.counter) + " " + str(parent_node_id) + " " + node.tag + " " + str(order) + " Link \r\n"
                self.result.append(s)
                nodeID = copy.deepcopy(self.counter)
                self.counter += 1

                for i in range(len(node)):
                    self.generate(node[i], nodeID, i)

    def WriteTXT(self, path):
        root = self.xmltree.getroot()
        self.generate(root, 0, 0)

        print(self.result)
        with codecs.open(path, "w", "utf-8")as f:
            f.writelines(self.result)

class mysql:
    """sql object to get data from mysql database"""
    def __init__(self, host = "118.24.5.150", user = "admin", password = "admin"):
        self.host = host
        self.user = user
        self.password = password
        self.database = None

    def __del__(self):
        if self.database is not None:
            self.database.close()

    def SAVE(self):
        if self.database is not None:
            self.database.commit()
        else:
            print("No useable database")

    def Database(self, database = "unittest"):
        self.database = pymysql.connect(self.host, self.user, self.password, database, charset = "utf8", local_infile = 1)
        if self.database.open:
            print("Database changed to:", database)
        else:
            print("connect database fail")

    def Execute(self, s):
        if self.database is None:
            print("No useable database")
            return
        else:
            cursor = self.database.cursor()
            cursor.execute(s)
            data = cursor.fetchall()
            cursor.close()
            return data

    def PExecute(self, s):
        data = self.Execute(s)
        for item in data:
            print(item)

class XpathExportData:
    """a new way to export data from exit xml file by tree"""
    # 维护两棵xml树, 数据xml树位于本地, id xml树位于数据库中(或从本地读取)遍历数据xml树, 通过xpath对应到id xml树, 将数据与id对应
    def __init__(self, database, dataxmlpath = "unit_test.xml", schemapath = "UnitTestSchema"):
        # 导入数据xml树
        self.LoadXML(dataxmlpath)
        # 导入id xml树
        self.LoadSchemaTree(database, schemapath)
        # print(etree.tostring(self.idxmltree.getroot(), pretty_print=True).decode("utf8"))
        # 导出的数据, 用空格分隔元素
        self.result = ["ModelID SchemaID Location Date \r\n"]
        # 导入节点信息字典
        self.Type = {}
        self.set_nodeinfo(schemapath)
    
    def LoadXML(self, path):
        self.dataxmltree = etree.parse(path)

    def LoadSchemaTree(self, database, path):
        # 从数据库中读取数据构建schema tree, 可考虑从本地读取提高速度
        self.database = database
        s1 = "SELECT ID, ParentID, OrderID, ElementName FROM " + path +";"
        nodes = list(self.database.Execute(s1))
        # 找到根结点
        for item in nodes:
            if(item[1] == 0):
                root = etree.Element(item[3], ID = str(item[0]))
                ID=str(item[0])
                self.idxmltree = etree.ElementTree(root)
                nodes.remove(item)
                break
        
        self.add_child(self.idxmltree.getroot(), nodes, ID)
        

    def add_child(self, node, data, ID):
            subdata = []
            flag = False
            for item in data:
                if(str(item[1]) == ID):
                    subdata.append(item)
                    flag = True
            if flag is True:
                subdata.sort(key = (lambda item:item[2]))
                for item in subdata:
                    child = etree.Element(item[3], ID = str(item[0]))
                    node.append(child)
                    ID=str(item[0])
                    data.remove(item)
                    self.add_child(child, data, ID)
                subdata.clear()

    def set_nodeinfo(self, mark):
        s = "SELECT ElementName, NodeType FROM " + mark + ";"
        datatype = self.database.Execute(s)
        for data in datatype:
            self.Type[data[0]] = data[1]

    def Export(self, ModelID):
        self.ModelID = ModelID
        root = self.dataxmltree.getroot()
        xpath = "//" + root.tag
        self.getdata(root, 0, xpath)

    def getdata(self, node, flag, xpath, locinf = "", arrparentnode = None):
        if flag == 0:
            # 不是复杂数组内的情况, flag为0
            if self.Type[node.tag] == "Link":
                # 连接节点，无数据
                for child in node:
                    cxpath = xpath + "/" + str(child.tag)
                    self.getdata(child, 0, cxpath)
            elif self.Type[node.tag] == "Data":
                # 简单数据节点，无子元素，带有简单数据
                xs = xpath + "/@ID"
                nodeid = (self.idxmltree.xpath(xs))[0]
                if node.text is not None:
                    s = str(self.ModelID) + " " + str(nodeid) + " 0 " + node.text + " \r\n"
                    self.result.append(s)
            else:
                # 数组情况，跳转至数组情况(flag == 1)
                self.getdata(node, 1, xpath)
        elif flag == 1:
            # 数组情况falg为1，设定数组父节点
            if arrparentnode is None:
                arrparentnode = node
            # 判断是否为复杂数组
            if node[0].tag == "array":
                # 多重数组情况(!只能处理同阶数组)
                # 判断是否为1维数组
                if len(node[0]) == 0:
                    # 1维数组，读取数据
                    for i in range(len(node)):
                        xs = xpath + "/@ID"
                        nodeid = (self.idxmltree.xpath(xs))[0]
                        if node[i].text is not None:
                            s = str(self.ModelID) + " "
                            s += str(nodeid) + " "
                            s += locinf + str(i) + " "
                            s += node[i].text + " \r\n"
                            self.result.append(s)
                else:
                    # 多维数组进行降阶
                    for i in range(len(node)):
                        sublocinf = locinf + str(i) + ","
                        self.getdata(node[i], 1, xpath, sublocinf, arrparentnode)                                    
            else:
                # 复杂数组情况,首级子节点必为连接结点
                for i in range(len(node)):
                    sublocinf = locinf + str(i) + ","
                    cxpath = xpath + "/" + str(node[i].tag)
                    print(sublocinf)
                    self.getdata(node[i], 2, cxpath, sublocinf, None)
        else:
            # 复杂数组内情况，flag为2
            if self.Type[node.tag] == "Link":
                # 连接节点，无数据
                for child in node:
                    cxpath = xpath + "/" + str(child.tag)
                    self.getdata(child, 2, cxpath, locinf, None)
            elif self.Type[node.tag] == "Data":
                # 简单数据节点，无子元素，带有简单数据
                xs = xpath + "/@ID"
                nodeid = (self.idxmltree.xpath(xs))[0]
                if node.text is not None:
                    s = str(self.ModelID) + " " + str(nodeid) + " " + locinf + "0 " + node.text + " \r\n"
                    self.result.append(s)
            else:
                # 数组情况，跳转至数组情况(flag == 1)
                self.getdata(node, 1, xpath, locinf, None)

    def WriteTXT(self, path):
        with codecs.open(path, "w", "utf-8")as f:
            f.writelines(self.result)

class xml_writer:
    """object organize xml form sql and write data to xml"""
    def __init__(self):
        self.Type = {}
        pass
    
    def SAVE(self, path = "test2.xml"):
        if self.xmltree is not None:
            with open(path, "wb+") as f:
                self.xmltree.write(f, encoding="utf-8", xml_declaration=True, pretty_print=True)

    def set_nodeinfo(self, mark):
        s = "SELECT ID, NodeType FROM " + mark + "Schema;"
        datatype = self.database.Execute(s)
        for data in datatype:
            self.Type[data[0]] = data[1]

    def WriteSchema(self, database, mark, modelid):
        # 先从数据库中抓取xml结构（如结构不变可考虑本地留存结构模板xml直接导入加快速度），再通过节点名称匹配注入数据
        self.database = database
        s1 = "SELECT ID, ParentID, OrderID, ElementName FROM " + mark +"Schema;"
        nodes = list(self.database.Execute(s1))
        # 找到根结点
        for item in nodes:
            if(item[1] == 0):
                root = etree.Element(item[3], ID = str(item[0]))
                ID=str(item[0])
                self.xmltree = etree.ElementTree(root)
                nodes.remove(item)
                break
        
        self.add_child(self.xmltree.getroot(), nodes, ID)
        self.set_nodeinfo(mark)
    
    def Organize(self, database, mark, modelid):
        # 先从数据库中抓取xml结构（如结构不变可考虑本地留存结构模板xml直接导入加快速度），再通过节点名称匹配注入数据
        self.database = database
        s1 = "SELECT ID, ParentID, OrderID, ElementName FROM " + mark +"Schema;"
        nodes = list(self.database.Execute(s1))
        # 找到根结点
        for item in nodes:
            if(item[1] == 0):
                root = etree.Element(item[3], ID = str(item[0]))
                ID=str(item[0])
                self.xmltree = etree.ElementTree(root)
                nodes.remove(item)
                break
        
        self.add_child(self.xmltree.getroot(), nodes, ID)

        self.set_nodeinfo(mark)

        sqlpath = "SELECT " + mark + "Schema.ID, " + mark + "Data.location, "+ mark + "Data.Data "
        sqlpath += "FROM " + mark + "Schema, " + mark + "Data "
        sqlpath += "WHERE " + mark + "Data.SchemaID = " + mark + "Schema.ID && "+ mark + "Data.ModelID = " + str(modelid) + ";"
        data = list(self.database.Execute(sqlpath))
        # sqlpath1 = "SELECT " + mark + "Schema.ElementName, " + mark + "Data.location, "+ mark + "Data.Data "
        # sqlpath1 += "FROM " + mark + "Schema, " + mark + "Data "
        # sqlpath1 += "WHERE " + mark + "Data.SchemaID = " + mark + "Schema.ID && "+ mark + "Data.ModelID = " + str(modelid) + ";"
        # data1 = list(self.database.Execute(sqlpath1))
        # print(data)
        # print(data1)
        # self.write_data(self.xmltree.getroot(), data)
        
        write_node_data(self.xmltree.getroot(), self.Type, data)
        # print(etree.tostring(root, pretty_print=True).decode("utf8"))
        print(data)

    def add_child(self, node, data, ID):
        subdata = []
        flag = False
        for item in data:
            if(str(item[1]) == ID):
                subdata.append(item)
                flag = True
        if flag is True:
            subdata.sort(key = (lambda item:item[2]))
            for item in subdata:
                child = etree.Element(item[3], ID = str(item[0]))
                node.append(child)
                ID=str(item[0])
                data.remove(item)
                self.add_child(child, data, ID)
            subdata.clear()

def write_array_data(node, data):
    if len(data) == 0:
        return
    else:
        if len(data[0][1]) == 1:
            # 一维数组，写入数据
            data.sort(key = (lambda item:item[1]))
            for item in data:
                anode = etree.Element("array")
                anode.text = item[2]
                node.append(anode)
        else:
            # 多维数组，进行降维
            nodelist = [[]]
            for i in range(len(data)):
                while int(data[i][1][0]) >= len(nodelist):
                    nodelist.append([])
                index = int(data[i][1].pop(0))
                nodelist[index].append(data[i])
            
            for i in range(len(nodelist)):
                s = "array" + str(i)
                croot = etree.Element(s)
                node.append(croot)
                write_array_data(croot, nodelist[i])

def write_node_data(node, node_data_type, data):
    if node_data_type[int(node.get("ID"))] == "Link":
        for child in node:
            write_node_data(child, node_data_type, data)
    elif node_data_type[int(node.get("ID"))] == "Data":
        for item in data:
            if int(node.get("ID")) == int(item[0]):
                node.text = item[2]
                data.remove(item)
                break
    else:
        if len(node) == 0:
            # 多维数组情况
            subdata = []
            deletdata = []
            # 取出数组数据，将location转换为list[int]
            for item in data:
                if int(node.get("ID")) == int(item[0]):
                    deletdata.append(item)
                    # location转换为list[int]
                    litem  = list(item)
                    locs = item[1]
                    if isinstance(locs,str):
                        subs = locs.split(",")
                        for i in subs:
                            i = int(i)
                    
                        litem[1] = subs
                    subdata.append(litem)            
            # 删除data中的重复数据
            for item in deletdata:
                data.remove(item)
            deletdata.clear()
            # 创建array节点写入数据
            write_array_data(node, subdata)    
        else:
            # 复杂数组情况，deepcopy数组根结点，分组写入数据
            subdata = []
            deletdata = []
            nodelist = []
            # 获取复杂节点下的所有数据
            #  获取复杂节点下的所有数据节点名称
            subdatanode(node, node_data_type, nodelist)
            #  获取数据节点数据
            for datanode in nodelist:
                for item in data:
                    if(datanode == int(item[0])):
                        deletdata.append(item)
                        litem  = list(item)
                        locs = item[1]
                        subs = locs.split(",")
                        for i in subs:
                            i = int(i)
                        litem[1] = subs
                        subdata.append(litem)
                # 删除data中的重复数据
                for item in deletdata:
                    data.remove(item)
                deletdata.clear()
            # 将数据按location分组
            datalist = [[]]
            for i in range(len(subdata)):
                while int(subdata[i][1][0]) >= len(datalist):
                    datalist.append([])
                index = int(subdata[i][1].pop(0))
                datalist[index].append(subdata[i])
            #  写入数据
            while len(node) < len(datalist):
                ctree = copy.deepcopy(node[0])
                node.append(ctree)
            for i in range(len(datalist)):                
                write_node_data(node[i], node_data_type, datalist[i])

def subdatanode(node, node_data_type, nodelist):
    for child in node:
        if node_data_type[int(child.get("ID"))] == "Link":
            for child in node:
                subdatanode(child, node_data_type, nodelist)
        elif node_data_type[int(child.get("ID"))] == "Data":
            nodelist.append(int(child.get("ID")))
        else:
            if len(child) == 0:
                nodelist.append(int(child.get("ID")))
            else:
                subdatanode(child, node_data_type, nodelist)
            
    
if __name__=="__main__":
    start =time.clock()

    # s = SchemaGenerator("../saturation/saturation.xml")
    # s.WriteTXT("../saturation/saturationschema.txt")

    # z = SchemaGenerator("unit_test.xml")
    # z.WriteTXT("UnitTestSchema.txt")
    
    x = mysql("localhost", "root", "root")
    x.Database("saturation")
    
    # h = XpathExportData(x, "../saturation/saturation.xml", "saturationschema")
    # h.Export(1)
    # h.WriteTXT("../saturation/xpathdata.txt")
    # print(h.result)
    
    k = xml_writer()
    k.Organize(x, "Saturation", 1)
    k.SAVE("../saturation/sql.xml")

    # j = xml_writer()
    # j.WriteSchema(x, 'sc', 1)
    # j.SAVE("schema.xml")
    
    end = time.clock()
    print('Running time: %s Seconds'%(end-start))
